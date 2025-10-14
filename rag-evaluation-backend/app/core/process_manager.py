"""
进程管理器 - 用于控制EvalScope任务的启动、暂停和继续
"""
import os
import signal
import psutil
import json
import time
import threading
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 全局文件锁字典，按task_id区分
_file_locks: Dict[int, threading.Lock] = {}
_locks_lock = threading.Lock()


class ProcessManager:
    """进程管理器"""
    
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.process_info_file = f"./outputs/evalscope_task_{task_id}/process_info.json"
        self.processes: Dict[str, int] = {}  # dataset_name -> pid
        
        # 获取或创建该任务的文件锁
        with _locks_lock:
            if task_id not in _file_locks:
                _file_locks[task_id] = threading.Lock()
            self.file_lock = _file_locks[task_id]
        
    def save_process_info(self, dataset_name: str, pid: int, cmd_args: List[str]):
        """保存进程信息（线程安全）"""
        try:
            # 使用文件锁保证并发安全
            with self.file_lock:
                os.makedirs(os.path.dirname(self.process_info_file), exist_ok=True)
                
                process_info = {
                    "task_id": self.task_id,
                    "dataset_name": dataset_name,
                    "pid": pid,
                    "cmd_args": cmd_args,
                    "start_time": time.time(),
                    "status": "running"
                }
                
                # 读取现有信息
                if os.path.exists(self.process_info_file):
                    with open(self.process_info_file, 'r') as f:
                        all_info = json.load(f)
                else:
                    all_info = {"processes": []}
                
                # 更新或添加进程信息
                updated = False
                for i, info in enumerate(all_info["processes"]):
                    if info["dataset_name"] == dataset_name:
                        all_info["processes"][i] = process_info
                        updated = True
                        break
                
                if not updated:
                    all_info["processes"].append(process_info)
                
                # 保存到文件
                with open(self.process_info_file, 'w') as f:
                    json.dump(all_info, f, indent=2)
                
                self.processes[dataset_name] = pid
                logger.info(f"保存进程信息: {dataset_name} -> PID {pid}")
            
        except Exception as e:
            logger.error(f"保存进程信息失败: {e}")
    
    def load_process_info(self) -> Dict[str, Dict]:
        """加载进程信息"""
        try:
            if not os.path.exists(self.process_info_file):
                return {}
            
            with open(self.process_info_file, 'r') as f:
                data = json.load(f)
                return {info["dataset_name"]: info for info in data.get("processes", [])}
        except Exception as e:
            logger.error(f"加载进程信息失败: {e}")
            return {}
    
    def pause_task(self) -> Tuple[bool, List[str]]:
        """暂停任务 - 撤销Celery任务并终止相关进程"""
        try:
            # 1. 撤销Celery任务
            celery_revoked = self._revoke_celery_task()
            
            # 2. 终止evalscope进程
            process_info = self.load_process_info()
            terminated_processes = []
            
            for dataset_name, info in process_info.items():
                pid = info["pid"]
                
                # 检查进程是否存在
                if not psutil.pid_exists(pid):
                    logger.warning(f"进程 {pid} ({dataset_name}) 已不存在")
                    continue
                
                try:
                    # 获取进程对象
                    process = psutil.Process(pid)
                    
                    # 检查进程是否还在运行
                    if process.is_running():
                        # 终止进程及其子进程
                        children = process.children(recursive=True)
                        for child in children:
                            try:
                                child.terminate()
                                logger.info(f"终止子进程: {child.pid}")
                            except psutil.NoSuchProcess:
                                pass
                        
                        # 终止主进程
                        process.terminate()
                        
                        # 等待进程结束
                        try:
                            process.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            # 强制杀死进程
                            process.kill()
                            logger.warning(f"强制终止进程: {pid}")
                        
                        terminated_processes.append(dataset_name)
                        logger.info(f"成功终止进程: {dataset_name} (PID: {pid})")
                    
                except psutil.NoSuchProcess:
                    logger.warning(f"进程 {pid} ({dataset_name}) 已不存在")
                except Exception as e:
                    logger.error(f"终止进程 {pid} ({dataset_name}) 失败: {e}")
            
            # 更新进程状态
            self._update_process_status("paused")
            
            # 汇总结果
            result_messages = []
            if celery_revoked:
                result_messages.append("Celery任务已撤销")
            if terminated_processes:
                result_messages.extend(terminated_processes)
            elif process_info:
                result_messages.append("所有进程已自然结束")
            
            return True, result_messages
            
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            return False, []
    
    def _revoke_celery_task(self) -> bool:
        """撤销Celery任务"""
        try:
            from app.tasks.evalscope_tasks import celery_app
            
            # 获取任务ID（从数据库或进程信息中）
            celery_task_id = self._get_celery_task_id()
            if not celery_task_id:
                logger.warning("未找到Celery任务ID")
                return False
            
            # 撤销任务
            celery_app.control.revoke(celery_task_id, terminate=True)
            logger.info(f"成功撤销Celery任务: {celery_task_id}")
            return True
            
        except Exception as e:
            logger.error(f"撤销Celery任务失败: {e}")
            return False
    
    def _get_celery_task_id(self) -> str:
        """获取Celery任务ID"""
        try:
            # 从进程信息文件获取
            process_info = self.load_process_info()
            for info in process_info.values():
                if 'celery_task_id' in info:
                    return info['celery_task_id']
            
            # 从数据库获取（仅从extra_metadata）
            try:
                from app.db.base import SessionLocal
                from sqlalchemy import text
                
                db = SessionLocal()
                try:
                    # 直接查询extra_metadata字段
                    result = db.execute(
                        text("SELECT extra_metadata FROM evalscope_tasks WHERE id = :task_id"),
                        {"task_id": self.task_id}
                    ).fetchone()
                    
                    if result and result[0]:
                        import json
                        metadata = result[0] if isinstance(result[0], dict) else json.loads(result[0])
                        if 'celery_task_id' in metadata:
                            return metadata['celery_task_id']
                finally:
                    db.close()
            except Exception as db_error:
                logger.warning(f"从数据库获取Celery任务ID失败: {db_error}")
            
            return None
            
        except Exception as e:
            logger.error(f"获取Celery任务ID失败: {e}")
            return None
    
    def resume_task(self) -> Tuple[bool, List[str]]:
        """继续任务 - 检查现有结果并返回可继续的数据集"""
        try:
            process_info = self.load_process_info()
            resumable_datasets = []
            need_new_process = False
            
            # 检查是否有运行中的进程
            running_processes = []
            for dataset_name, info in process_info.items():
                pid = info.get("pid")
                if pid and psutil.pid_exists(pid):
                    try:
                        process = psutil.Process(pid)
                        if process.is_running():
                            running_processes.append(dataset_name)
                            logger.info(f"数据集 {dataset_name} 的进程 {pid} 仍在运行")
                    except psutil.NoSuchProcess:
                        logger.info(f"数据集 {dataset_name} 的进程 {pid} 已不存在")
            
            # 如果没有运行中的进程，需要启动新进程
            if not running_processes:
                need_new_process = True
                logger.info("没有运行中的进程，需要启动新进程")
            
            # 检查现有结果
            for dataset_name, info in process_info.items():
                if self._has_existing_results(dataset_name):
                    resumable_datasets.append(dataset_name)
                    logger.info(f"数据集 {dataset_name} 有现有结果，可以继续")
                else:
                    logger.info(f"数据集 {dataset_name} 无现有结果，需要重新开始")
            
            # 如果没有可继续的数据集，但有进程信息，说明需要重新开始
            if not resumable_datasets and process_info:
                logger.info("没有可继续的数据集，但存在进程信息，将重新开始所有数据集")
                resumable_datasets = list(process_info.keys())
            
            # 更新进程状态
            self._update_process_status("resumed")
            
            return True, resumable_datasets
            
        except Exception as e:
            logger.error(f"继续任务失败: {e}")
            return False, []
    
    def _has_existing_results(self, dataset_name: str) -> bool:
        """检查是否有现有结果"""
        try:
            # 检查预测结果文件 - 支持多种目录结构
            base_dir = f"./outputs/evalscope_task_{self.task_id}/{dataset_name}"
            
            # 检查直接路径
            predictions_dir = f"{base_dir}/predictions"
            if os.path.exists(predictions_dir):
                for root, dirs, files in os.walk(predictions_dir):
                    if any(f.endswith('.jsonl') for f in files):
                        logger.info(f"在 {root} 找到 {len([f for f in files if f.endswith('.jsonl')])} 个jsonl文件")
                        return True
            
            # 检查带时间戳的路径 (如: 20251013_231638/predictions)
            if os.path.exists(base_dir):
                for item in os.listdir(base_dir):
                    item_path = os.path.join(base_dir, item)
                    if os.path.isdir(item_path):
                        predictions_subdir = os.path.join(item_path, "predictions")
                        if os.path.exists(predictions_subdir):
                            for root, dirs, files in os.walk(predictions_subdir):
                                if any(f.endswith('.jsonl') for f in files):
                                    logger.info(f"在 {root} 找到 {len([f for f in files if f.endswith('.jsonl')])} 个jsonl文件")
                                    return True
            
            # 检查评估结果文件
            reviews_dir = f"{base_dir}/reviews"
            if os.path.exists(reviews_dir):
                for root, dirs, files in os.walk(reviews_dir):
                    if any(f.endswith('.jsonl') for f in files):
                        logger.info(f"在 {root} 找到 {len([f for f in files if f.endswith('.jsonl')])} 个jsonl文件")
                        return True
            
            logger.info(f"数据集 {dataset_name} 没有找到现有结果")
            return False
            
        except Exception as e:
            logger.error(f"检查现有结果失败: {e}")
            return False
    
    def _update_process_status(self, status: str):
        """更新进程状态"""
        try:
            if not os.path.exists(self.process_info_file):
                return
            
            with open(self.process_info_file, 'r') as f:
                data = json.load(f)
            
            # 更新所有进程状态
            for info in data.get("processes", []):
                info["status"] = status
                if status == "paused":
                    info["paused_at"] = time.time()
                elif status == "resumed":
                    info["resumed_at"] = time.time()
            
            with open(self.process_info_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"更新进程状态失败: {e}")
    
    def get_task_status(self) -> Dict[str, any]:
        """获取任务状态"""
        try:
            process_info = self.load_process_info()
            if not process_info:
                return {"status": "not_started", "processes": []}
            
            running_processes = []
            paused_processes = []
            
            for dataset_name, info in process_info.items():
                pid = info["pid"]
                status = info.get("status", "unknown")
                
                # 检查进程是否还在运行
                if psutil.pid_exists(pid):
                    try:
                        process = psutil.Process(pid)
                        if process.is_running():
                            running_processes.append({
                                "dataset_name": dataset_name,
                                "pid": pid,
                                "status": "running",
                                "start_time": info.get("start_time"),
                                "cmd_args": info.get("cmd_args", [])
                            })
                        else:
                            paused_processes.append({
                                "dataset_name": dataset_name,
                                "pid": pid,
                                "status": "stopped"
                            })
                    except psutil.NoSuchProcess:
                        paused_processes.append({
                            "dataset_name": dataset_name,
                            "pid": pid,
                            "status": "not_found"
                        })
                else:
                    paused_processes.append({
                        "dataset_name": dataset_name,
                        "pid": pid,
                        "status": "not_found"
                    })
            
            return {
                "status": "running" if running_processes else "paused",
                "running_processes": running_processes,
                "paused_processes": paused_processes,
                "total_processes": len(process_info)
            }
            
        except Exception as e:
            logger.error(f"获取任务状态失败: {e}")
            return {"status": "error", "error": str(e)}
    
    def cleanup(self):
        """清理进程信息文件"""
        try:
            if os.path.exists(self.process_info_file):
                os.remove(self.process_info_file)
                logger.info(f"清理进程信息文件: {self.process_info_file}")
        except Exception as e:
            logger.error(f"清理进程信息文件失败: {e}")


def get_process_manager(task_id: int) -> ProcessManager:
    """获取进程管理器实例"""
    return ProcessManager(task_id)
