"""
进程管理器 - 用于控制EvalScope任务的启动、暂停和继续
"""
import os
import signal
import psutil
import json
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ProcessManager:
    """进程管理器"""
    
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.process_info_file = f"./outputs/evalscope_task_{task_id}/process_info.json"
        self.processes: Dict[str, int] = {}  # dataset_name -> pid
        
    def save_process_info(self, dataset_name: str, pid: int, cmd_args: List[str]):
        """保存进程信息"""
        try:
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
        """暂停任务 - 终止所有相关进程"""
        try:
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
            
            return True, terminated_processes
            
        except Exception as e:
            logger.error(f"暂停任务失败: {e}")
            return False, []
    
    def resume_task(self) -> Tuple[bool, List[str]]:
        """继续任务 - 检查现有结果并返回可继续的数据集"""
        try:
            process_info = self.load_process_info()
            resumable_datasets = []
            
            for dataset_name, info in process_info.items():
                # 检查是否有现有结果
                if self._has_existing_results(dataset_name):
                    resumable_datasets.append(dataset_name)
                    logger.info(f"数据集 {dataset_name} 有现有结果，可以继续")
                else:
                    logger.info(f"数据集 {dataset_name} 无现有结果，需要重新开始")
            
            # 更新进程状态
            self._update_process_status("resumed")
            
            return True, resumable_datasets
            
        except Exception as e:
            logger.error(f"继续任务失败: {e}")
            return False, []
    
    def _has_existing_results(self, dataset_name: str) -> bool:
        """检查是否有现有结果"""
        try:
            # 检查预测结果文件
            predictions_dir = f"./outputs/evalscope_task_{self.task_id}/{dataset_name}/predictions"
            if os.path.exists(predictions_dir):
                # 检查是否有.jsonl文件
                for root, dirs, files in os.walk(predictions_dir):
                    if any(f.endswith('.jsonl') for f in files):
                        return True
            
            # 检查评估结果文件
            reviews_dir = f"./outputs/evalscope_task_{self.task_id}/{dataset_name}/reviews"
            if os.path.exists(reviews_dir):
                for root, dirs, files in os.walk(reviews_dir):
                    if any(f.endswith('.jsonl') for f in files):
                        return True
            
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
