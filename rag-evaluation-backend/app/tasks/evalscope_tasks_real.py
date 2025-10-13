"""
EvalScope真实评测异步任务 - 调用命令行工具
"""
import os
import sys
import subprocess
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List
from pathlib import Path

# 导入性能配置
from app.core.config import settings
from app.core.process_manager import ProcessManager

# Celery配置
try:
    from celery import Celery
    
    # ==================== 环境变量验证 ====================
    # 目的：确保Celery配置完整，避免使用默认值导致的隐藏问题
    # 问题定位：如果这里抛出ValueError，说明环境变量未正确配置
    # 解决方案：在启动脚本或.env文件中设置 CELERY_BROKER_URL 和 CELERY_RESULT_BACKEND
    
    # 尝试从配置文件加载环境变量
    config_file = "performance_config_optimized.env"
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key.startswith('CELERY_'):
                        os.environ[key] = value
    
    broker_url = os.getenv("CELERY_BROKER_URL")
    backend_url = os.getenv("CELERY_RESULT_BACKEND")
    
    # 检查Broker URL（消息队列地址）
    if not broker_url:
        raise ValueError("环境变量 CELERY_BROKER_URL 未设置。请配置Redis连接URL，例如: redis://localhost:6379/0")
    
    # 检查Backend URL（结果存储地址）
    if not backend_url:
        raise ValueError("环境变量 CELERY_RESULT_BACKEND 未设置。请配置Redis连接URL，例如: redis://localhost:6379/0")
    
    # 创建Celery应用实例（使用验证过的环境变量）
    celery_app = Celery(
        "evalscope_real_tasks",
        broker=broker_url,
        backend=backend_url
    )
    
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=7200,  # 2小时超时
        task_soft_time_limit=7000,  # 软超时
    )
    
    CELERY_AVAILABLE = True
    print("✅ Celery配置完成，支持真实评测")
    
# ==================== 异常处理 ====================
# 捕获两种可能的错误：
# 1. ImportError: Celery包未安装 -> 提示安装celery[redis]
# 2. ValueError: 环境变量未配置 -> 提示配置CELERY_BROKER_URL和CELERY_RESULT_BACKEND
except (ImportError, ValueError) as e:
    CELERY_AVAILABLE = False
    celery_app = None  # 确保celery_app被定义，即使Celery不可用
    
    # 根据异常类型输出不同的错误信息，便于快速定位问题
    if isinstance(e, ImportError):
        print("❌ Celery未安装，真实评测不可用")
        print("   解决方案: pip install celery[redis]")
    else:
        print(f"❌ Celery配置错误: {e}")
        print("   解决方案: 检查环境变量或启动脚本中的Redis配置")


def get_db_session():
    """获取数据库会话"""
    # 确保所有模型都被导入，避免外键约束问题
    from app.models import user, evalscope_task
    from app.db.base import SessionLocal
    return SessionLocal()


def is_local_model(model_id: str) -> bool:
    """判断是否为本地模型"""
    if not model_id:
        return False
    
    # 本地模型的特征：
    # 1. 包含 "/" 分隔符（如 Qwen/Qwen2.5-0.5B-Instruct）
    # 2. 不包含常见的API服务标识
    # 3. 不是用户配置的模型
    
    # 用户配置的模型（user_config_xxx格式）通常是API模型
    if model_id.startswith('config:') or model_id.startswith('user_config_'):
        return False
    
    # API模型的特征标识（精确匹配）
    api_model_patterns = [
        'qwen-plus', 'qwen-max', 'qwen-turbo', 'qwen3-',
        'claude-', 'gemini-',
        'openai', 'anthropic'
    ]
    
    # GPT模型特殊处理：只有以gpt-开头的才是API模型
    if model_id.lower().startswith('gpt-'):
        return False
    
    # 如果包含其他API模型标识，则为API模型
    if any(pattern in model_id.lower() for pattern in api_model_patterns):
        return False
    
    # 如果包含 "/" 分隔符，通常是本地模型（HuggingFace格式）
    if '/' in model_id:
        return True
    
    # 其他情况默认为本地模型
    return True


class ProgressReporter:
    """进度报告器 - 带智能节流优化"""
    def __init__(self, db, task_id: int):
        self.db = db
        self.task_id = task_id
        self.dataset_progress = {}
        self.current_phase = 'initializing'
        self.total_datasets = 0
        self.completed_datasets = 0
        # 性能优化：节流控制
        self.last_db_update = 0  # 上次数据库更新时间
        self.last_progress = 0   # 上次进度值
        self.pending_update = None  # 待更新的数据（节流期间暂存）
    
    def initialize_datasets(self, datasets: list):
        """初始化数据集进度追踪"""
        self.total_datasets = len(datasets)
        for dataset in datasets:
            self.dataset_progress[dataset] = {
                'name': dataset,
                'status': 'waiting',
                'progress': 0,
                'current_step': None,
                'total_samples': None,
                'completed_samples': 0,
                'start_time': None,
                'end_time': None
            }
    
    def update_dataset_progress(self, dataset_name: str, progress: int, status: str = None, 
                               current_step: str = None, total_samples: int = None, 
                               completed_samples: int = None):
        """更新特定数据集的进度"""
        if dataset_name in self.dataset_progress:
            dataset_info = self.dataset_progress[dataset_name]
            dataset_info['progress'] = min(progress, 100)
            
            if status:
                dataset_info['status'] = status
                if status == 'running' and not dataset_info['start_time']:
                    dataset_info['start_time'] = datetime.now(timezone.utc).isoformat()
                elif status == 'completed' and not dataset_info['end_time']:
                    dataset_info['end_time'] = datetime.now(timezone.utc).isoformat()
                    dataset_info['progress'] = 100
                    
            if current_step:
                dataset_info['current_step'] = current_step
            if total_samples is not None:
                dataset_info['total_samples'] = total_samples
            if completed_samples is not None:
                dataset_info['completed_samples'] = completed_samples
    
    def set_phase(self, phase: str):
        """设置当前执行阶段"""
        self.current_phase = phase
    
    def get_detailed_progress(self):
        """获取详细进度信息"""
        completed_count = sum(1 for ds in self.dataset_progress.values() if ds['status'] == 'completed')
        
        return {
            'overall_progress': self._calculate_overall_progress(),
            'current_dataset': self._get_current_dataset(),
            'total_datasets': self.total_datasets,
            'completed_datasets': completed_count,
            'dataset_progress': list(self.dataset_progress.values()),
            'phase': self.current_phase
        }
    
    def _calculate_overall_progress(self):
        """计算整体进度"""
        if not self.dataset_progress:
            return 0
        
        # 基于阶段的基础进度
        phase_progress = {
            'initializing': 0,
            'loading_model': 10,
            'evaluating': 15,
            'processing_results': 95,
            'completed': 100
        }
        base_progress = phase_progress.get(self.current_phase, 0)
        
        # 数据集评测进度 (占总进度的80%)
        if self.current_phase == 'evaluating' and self.dataset_progress:
            dataset_avg_progress = sum(ds['progress'] for ds in self.dataset_progress.values()) / len(self.dataset_progress)
            eval_progress = 15 + (dataset_avg_progress * 0.8)  # 15-95%
            return min(int(eval_progress), 95)
        
        return base_progress
    
    def _get_current_dataset(self):
        """获取当前正在执行的数据集"""
        for ds in self.dataset_progress.values():
            if ds['status'] == 'running':
                return ds['name']
        return None
    
    def update_progress(self, progress: int, message: str = "", dataset_name: str = None, force: bool = False):
        """更新进度（带智能节流优化）"""
        from app.models.evalscope_task import EvalScopeTask
        
        # 如果指定了数据集，更新数据集进度（内存中）
        if dataset_name and dataset_name in self.dataset_progress:
            self.update_dataset_progress(dataset_name, progress)
        
        # 计算整体进度
        overall_progress = self._calculate_overall_progress() if self.dataset_progress else progress
        
        # === 性能优化：智能节流 ===
        # 1. 关键节点强制更新（0%, 100%, 或force=True）
        # 2. 进度变化不足5%不更新
        # 3. 距离上次更新时间不足配置间隔不更新
        current_time = time.time()
        progress_changed = abs(overall_progress - self.last_progress) >= 5
        time_elapsed = (current_time - self.last_db_update) >= settings.EVALSCOPE_DB_UPDATE_INTERVAL
        is_milestone = overall_progress in [0, 100]
        
        should_update = force or is_milestone or (progress_changed and time_elapsed)
        
        # 如果不需要更新，只暂存数据并打印日志
        if not should_update:
            self.pending_update = (overall_progress, message, dataset_name)
            if message:
                print(f"[Task {self.task_id}] {overall_progress}% - {message} (节流中)")
            return
        
        # === 执行数据库更新 ===
        task = self.db.query(EvalScopeTask).filter(
            EvalScopeTask.id == self.task_id
        ).first()
        
        if task:
            task.progress = min(overall_progress, 100)
            
            # 存储详细进度到元数据
            detailed_progress = self.get_detailed_progress()
            if message:
                detailed_progress['message'] = message
            
            # 更新任务的详细进度信息到extra_metadata
            if not task.extra_metadata:
                task.extra_metadata = {}
            task.extra_metadata['detailed_progress_metadata'] = detailed_progress
            
            if message:
                print(f"[Task {self.task_id}] {overall_progress}% - {message}")
                if dataset_name:
                    print(f"  └── 数据集 {dataset_name}: {progress}%")
            
            self.db.commit()
            
            # 更新节流状态
            self.last_db_update = current_time
            self.last_progress = overall_progress
            self.pending_update = None
            
            # === 性能优化：非阻塞WebSocket发送 ===
            # 使用线程池异步发送，超时后自动放弃
            try:
                import threading
                from app.tasks.evalscope_tasks import send_progress_update
                import asyncio
                
                def send_ws_async():
                    """在独立线程中发送WebSocket消息"""
                    try:
                        # 设置超时
                        import signal
                        
                        def timeout_handler(signum, frame):
                            raise TimeoutError("WebSocket发送超时")
                        
                        # 仅在非Windows系统使用signal
                        if hasattr(signal, 'SIGALRM'):
                            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                            signal.alarm(int(settings.EVALSCOPE_WEBSOCKET_TIMEOUT))
                        
                        try:
                            asyncio.run(send_progress_update(
                                self.task_id, overall_progress, message, detailed_progress
                            ))
                        finally:
                            if hasattr(signal, 'SIGALRM'):
                                signal.alarm(0)
                                signal.signal(signal.SIGALRM, old_handler)
                    except Exception:
                        pass  # 静默失败，不影响主流程
                
                # 使用守护线程发送（主线程结束时自动终止）
                ws_thread = threading.Thread(target=send_ws_async, daemon=True)
                ws_thread.start()
                
            except Exception:
                # WebSocket发送失败不影响主流程
                pass
    
    def log(self, level: str, message: str):
        """记录日志"""
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[Task {self.task_id}] [{timestamp}] [{level}] {message}")


def count_completed_samples(work_dir: Path) -> int:
    """
    统计指定工作目录中已完成的样本数量
    通过读取 predictions 目录下的 jsonl 文件行数来统计
    
    Args:
        work_dir: 工作目录路径
        
    Returns:
        已完成的样本数量
    """
    import glob
    
    try:
        # 查找所有 prediction 文件
        prediction_pattern = str(work_dir / "predictions" / "**" / "*.jsonl")
        prediction_files = glob.glob(prediction_pattern, recursive=True)
        
        total_lines = 0
        for file_path in prediction_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # 统计非空行
                    lines = sum(1 for line in f if line.strip())
                    total_lines += lines
            except Exception as e:
                print(f"读取文件 {file_path} 时出错: {e}")
                continue
        
        return total_lines
    except Exception as e:
        print(f"统计样本数时出错: {e}")
        return 0


def parse_evalscope_output(stdout_lines: List[str], task_id: int = None) -> List[Dict]:
    """解析EvalScope命令行输出"""
    results = []
    
    # 查找结果表格 - 支持多种表格格式
    in_table = False
    for i, line in enumerate(stdout_lines):
        line = line.strip()
        
        # 检测旧格式表格开始
        if "| Model Name" in line and "| Score |" in line:
            in_table = True
            continue
            
        # 检测新格式表格开始 (EvalScope新版本)
        if ("| Model" in line and "| Dataset" in line and "| Metric" in line) or \
           ("+-----------+-----------+----------" in line):
            in_table = True
            continue
        
        # 检测表格结束
        if in_table and (line.startswith('+-----------+-----------+----------') or 
                        (line.startswith('+') and '=' in line)):
            # 检查下一行是否还有数据，如果没有则结束表格
            if i + 1 >= len(stdout_lines) or not stdout_lines[i + 1].strip().startswith('|'):
                in_table = False
            continue
        
        # 解析数据行
        if in_table and line.startswith('|') and not line.startswith('+='):
            try:
                parts = [p.strip() for p in line.split('|') if p.strip()]
                
                # 新格式：| Model | Dataset | Metric | Subset | Num | Score | Cat.0 |
                if len(parts) >= 6:
                    model_name = parts[0]
                    dataset = parts[1] 
                    metric = parts[2]
                    subset = parts[3] if len(parts) > 3 else 'main'
                    
                    # 解析样本数量
                    num_samples = None
                    if len(parts) > 4:
                        try:
                            num_samples = int(parts[4])
                        except (ValueError, TypeError):
                            num_samples = None
                    
                    # 解析分数
                    score = None
                    if len(parts) > 5:
                        try:
                            score_str = parts[5].replace('%', '')
                            score = float(score_str)
                            # 保持分数在0-1范围，不转换为百分比
                            # 前端会统一处理百分比显示
                        except (ValueError, TypeError):
                            score = None
                    
                    # 跳过OVERALL行，避免重复计算
                    if subset.upper() == 'OVERALL':
                        continue
                        
                    if score is not None:
                        results.append({
                            'benchmark': dataset,
                            'metric_name': metric,
                            'metric_value': score,
                            'category': parts[6] if len(parts) > 6 else 'default',
                            'subset_name': subset,
                            'num_samples': num_samples
                        })
                        
            except Exception as e:
                print(f"解析结果行失败: {line} -> {e}")
    
    # 如果没有解析到结果，尝试从JSON报告文件中读取
    if not results:
        print("INFO: 标准输出解析失败，尝试从JSON报告文件读取结果")
        work_dir = None
        
        # 从stdout_lines中查找工作目录
        for line in stdout_lines:
            if "Output directory:" in line and "outputs/" in line:
                # 格式: "Output directory: outputs/evalscope_task_56/20251011_100905"
                work_dir = line.split("outputs/")[1].strip() if "outputs/" in line else None
                print(f"INFO: 从日志找到工作目录: {work_dir}")
                break
        
        # 如果没有找到，使用当前任务ID构造
        if not work_dir and task_id:
            work_dir = f"evalscope_task_{task_id}"
            print(f"INFO: 使用默认工作目录: {work_dir}")
        
        if work_dir:
            try:
                import json
                from pathlib import Path
                
                # 改进路径查找逻辑 - 直接在工作目录下查找
                work_path = Path(f"outputs/{work_dir}")
                if not work_path.exists():
                    # 如果work_dir不存在，尝试查找evalscope_task_*目录
                    work_path = Path(f"outputs/evalscope_task_{task_id}")
                
                print(f"INFO: 搜索JSON文件路径: {work_path}")
                
                if work_path.exists():
                    # 查找所有JSON报告文件
                    json_files = list(work_path.glob("**/reports/*/*.json"))
                    print(f"INFO: 找到 {len(json_files)} 个JSON文件")
                    
                    for json_file in json_files:
                        print(f"INFO: 读取JSON文件: {json_file}")
                        with open(json_file, 'r', encoding='utf-8') as f:
                            report_data = json.load(f)
                            
                            if 'metrics' in report_data:
                                for metric in report_data['metrics']:
                                    # 处理子集数据 - 合并为数据集级别汇总
                                    if 'categories' in metric:
                                        for category in metric['categories']:
                                            if 'subsets' in category:
                                                # 为每个子集单独创建结果记录
                                                for subset in category['subsets']:
                                                    subset_score = subset['score']
                                                    subset_samples = subset['num']
                                                    
                                                    # 处理category.name可能是数组的情况
                                                    category_name = category.get('name', ['default'])
                                                    if isinstance(category_name, list) and len(category_name) > 0:
                                                        category_name = category_name[0]
                                                    elif not isinstance(category_name, str):
                                                        category_name = 'default'
                                                    
                                                    results.append({
                                                        'benchmark': report_data.get('dataset_name', 'unknown'),
                                                        'metric_name': metric.get('name', 'accuracy'),
                                                        'metric_value': subset_score,  # 保持0-1范围
                                                        'category': category_name,
                                                        'subset_name': subset['name'],  # 单独的子集名称
                                                        'num_samples': subset_samples
                                                    })
                                                    print(f"INFO: 添加子集结果: {report_data.get('dataset_name', 'unknown')} - {subset['name']} - {subset_score:.4f} ({subset_samples}样本)")
                                                
                                                # 同时添加加权平均结果
                                                total_samples = 0
                                                weighted_score_sum = 0
                                                subset_names = []
                                                
                                                for subset in category['subsets']:
                                                    subset_score = subset['score']
                                                    subset_samples = subset['num']
                                                    weighted_score_sum += subset_score * subset_samples
                                                    total_samples += subset_samples
                                                    subset_names.append(subset['name'])
                                                
                                                if total_samples > 0:
                                                    avg_score = weighted_score_sum / total_samples
                                                    
                                                    results.append({
                                                        'benchmark': report_data.get('dataset_name', 'unknown'),
                                                        'metric_name': metric.get('name', 'accuracy'),
                                                        'metric_value': avg_score,  # 保持0-1范围
                                                        'category': category_name,
                                                        'subset_name': 'average',  # 标记为平均分
                                                        'num_samples': total_samples
                                                    })
                                                    print(f"INFO: 添加平均结果: {report_data.get('dataset_name', 'unknown')} - 平均分 - {avg_score:.4f} ({total_samples}样本)")
                                    else:
                                        # 如果没有子集，直接使用metric数据
                                        score = metric.get('score', 0)  # 保持0-1范围
                                        results.append({
                                            'benchmark': report_data.get('dataset_name', 'unknown'),
                                            'metric_name': metric.get('name', 'accuracy'),
                                            'metric_value': score,
                                            'category': 'default',
                                            'subset_name': 'main',
                                            'num_samples': metric.get('num', 0)
                                        })
                                        print(f"INFO: 添加主结果: {report_data.get('dataset_name', 'unknown')} - main - {score:.4f} ({metric.get('num', 0)}样本)")
                                break
                else:
                    print(f"WARNING: 工作目录不存在: {work_path}")
                    
            except Exception as e:
                print(f"WARNING: 从JSON文件读取结果失败: {e}")
                import traceback
                traceback.print_exc()
    
    return results


@celery_app.task(bind=True, name='evalscope.run_real_evaluation')
def run_real_evaluation_task(self, task_id: int):
    """执行真实的EvalScope评测任务"""
    from app.models.evalscope_task import EvalScopeTask, EvalScopeResult
    
    # 添加任务取消检查支持
    def check_is_aborted():
        """检查任务是否被取消"""
        # Celery 5.x 使用 request.cancelled 属性
        return getattr(self.request, 'cancelled', False)
    
    db = get_db_session()
    reporter = ProgressReporter(db, task_id)
    
    try:
        # 1. 获取任务
        task = db.query(EvalScopeTask).filter(
            EvalScopeTask.id == task_id
        ).first()
        
        if not task:
            raise Exception(f"Task {task_id} not found")
        
        # 输出任务概览
        reporter.log("INFO", "")
        reporter.log("INFO", "=" * 80)
        reporter.log("INFO", f"🎯 开始执行真实评测任务")
        reporter.log("INFO", "=" * 80)
        reporter.log("INFO", f"📝 任务名称: {task.task_name}")
        reporter.log("INFO", f"🆔 任务ID: {task_id}")
        reporter.log("INFO", f"🤖 模型ID: {task.model_id}")
        reporter.log("INFO", f"📊 数据集数量: {len(task.datasets)}")
        reporter.log("INFO", f"📋 数据集列表: {', '.join(task.datasets)}")
        reporter.log("INFO", f"🔧 评测类型: {task.eval_type}")
        # limit存储在dataset_args中
        if task.dataset_args:
            limits = [task.dataset_args.get(ds, {}).get('limit') for ds in task.datasets if task.dataset_args.get(ds, {}).get('limit')]
            if limits:
                reporter.log("INFO", f"🔢 样本限制: {limits[0] if len(set(limits)) == 1 else limits}")
        reporter.log("INFO", "=" * 80)
        reporter.log("INFO", "")
        
        # 2. 更新状态为运行中
        task.status = 'running'
        task.started_at = datetime.now()
        task.celery_task_id = self.request.id  # 更新Celery任务ID
        if not task.extra_metadata:
            task.extra_metadata = {}
        task.extra_metadata['celery_task_id'] = self.request.id
        db.commit()
        
        # 初始化数据集进度追踪
        reporter.initialize_datasets(task.datasets)
        reporter.set_phase('initializing')
        reporter.update_progress(5, "初始化任务")
        
        # 3. 准备工作目录（如果不存在则创建）
        if not task.work_dir:
            work_dir = Path(f'./outputs/evalscope_task_{task_id}')
            work_dir.mkdir(parents=True, exist_ok=True)
            task.work_dir = str(work_dir)
            db.commit()
        else:
            work_dir = Path(task.work_dir)
            work_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查任务恢复状态 - 使用EvalScope的use_cache功能实现断点续评
        is_resumed = False
        if work_dir.exists():
            # 检查是否有部分完成的评测结果（在数据集子目录中）
            has_predictions = False
            for dataset_name in task.datasets:
                dataset_dir = work_dir / dataset_name
                if dataset_dir.exists():
                    # 查找最新的时间戳目录
                    timestamp_dirs = [d for d in dataset_dir.iterdir() if d.is_dir() and d.name.startswith('2025')]
                    if timestamp_dirs:
                        latest_dir = max(timestamp_dirs, key=lambda x: x.name)
                        predictions_dir = latest_dir / 'predictions'
                        if predictions_dir.exists() and any(predictions_dir.iterdir()):
                            has_predictions = True
                            break
            
            if has_predictions:
                is_resumed = True
                reporter.log("INFO", f"🔄 检测到任务恢复，将使用EvalScope断点续评功能继续执行")
                reporter.log("INFO", f"📁 工作目录: {work_dir}")
                reporter.log("INFO", f"📊 发现已有评测结果，将从断点继续")
        
        reporter.update_progress(10, "准备工作环境")
        
        # 4. 构建evalscope命令 - 支持多数据集并行处理
        # 修复模型ID格式问题 - 正确处理用户配置的模型
        model_id = task.model_id
        reporter.log("INFO", f"原始模型ID: {task.model_id}, eval_type: {task.eval_type}")
        
        # 首先检查并修复无效的模型ID（在判断模型类型之前）
        if not model_id or model_id in ['model', ''] or model_id.strip() == "":
            # 如果有用户配置，使用用户配置的API模型
            if hasattr(task, 'extra_metadata') and task.extra_metadata and task.extra_metadata.get('user_model_config'):
                user_config = task.extra_metadata['user_model_config']
                if user_config.get('model_name'):
                    model_id = user_config['model_name']
                    reporter.log("WARNING", f"⚠️ 模型ID无效 ({task.model_id})，从用户配置中提取: {model_id}")
                else:
                    error_msg = f"模型ID无效 ({task.model_id})，且用户配置中没有模型名称。请在【大模型管理】中正确配置模型。"
                    reporter.log("ERROR", error_msg)
                    raise Exception(error_msg)
            else:
                # 没有用户配置，报错要求用户配置
                error_msg = f"模型ID无效 ({task.model_id})，且没有找到用户配置。请在【大模型管理】中正确配置模型。"
                reporter.log("ERROR", error_msg)
                raise Exception(error_msg)
        
        # 处理用户配置的模型ID（格式: user_config_xxx）
        elif model_id and model_id.startswith('user_config_'):
            # 从用户配置中提取真实的模型名称
            if hasattr(task, 'extra_metadata') and task.extra_metadata and task.extra_metadata.get('user_model_config'):
                user_config = task.extra_metadata['user_model_config']
                if user_config.get('model_name'):
                    model_id = user_config['model_name']
                    reporter.log("INFO", f"✅ 从用户配置中提取模型名称: {model_id}")
                else:
                    # 如果用户配置中没有模型名称，报错
                    error_msg = f"用户配置 ({task.model_id}) 中没有模型名称。请在【大模型管理】中完善模型配置。"
                    reporter.log("ERROR", error_msg)
                    raise Exception(error_msg)
            else:
                # 如果没有用户配置，报错
                error_msg = f"模型ID ({task.model_id}) 指向用户配置，但未找到配置信息。请在【大模型管理】中正确配置模型。"
                reporter.log("ERROR", error_msg)
                raise Exception(error_msg)
        
        # 使用当前环境的Python（通过conda环境自动设置）
        # 优先使用环境变量，否则使用当前Python解释器
        conda_python = os.getenv('EVALSCOPE_PYTHON_PATH', sys.executable)
        
        # 检查是否支持并行处理（多个数据集）
        if len(task.datasets) > 1:
            reporter.log("INFO", f"🚀 检测到 {len(task.datasets)} 个数据集，启用并行处理")
            
            # 为每个数据集创建单独的命令
            dataset_commands = []
            for dataset in task.datasets:
                cmd_args = [
                    conda_python, '-m', 'evalscope.cli.cli', 'eval',
                    '--model', model_id,
                    '--datasets', dataset  # 单个数据集
                ]
                dataset_commands.append((dataset, cmd_args))
        else:
            # 单个数据集，使用原有逻辑
            cmd_args = [
                conda_python, '-m', 'evalscope.cli.cli', 'eval',
                '--model', model_id,
                '--datasets'
            ] + task.datasets
            dataset_commands = [("single", cmd_args)]
        
        # 为每个数据集命令添加参数
        def add_common_args(cmd_args, dataset_name=None):
            """为命令添加通用参数"""
            # 添加limit参数
            limit_value = None
            if task.dataset_args and dataset_name and dataset_name in task.dataset_args:
                dataset_config = task.dataset_args[dataset_name]
                if 'limit' in dataset_config:
                    limit_value = dataset_config['limit']
            elif task.dataset_args:
                # 如果没有特定数据集配置，使用第一个可用的limit
                for dataset in task.datasets:
                    if dataset in task.dataset_args:
                        dataset_config = task.dataset_args[dataset]
                        if 'limit' in dataset_config:
                            limit_value = dataset_config['limit']
                            break
            
            if limit_value:
                cmd_args.extend(['--limit', str(limit_value)])
            
            # eval_type参数将在主循环中添加，避免重复
            
            return cmd_args
        
        # 为所有数据集命令添加通用参数
        for i, (dataset_name, cmd_args) in enumerate(dataset_commands):
            dataset_commands[i] = (dataset_name, add_common_args(cmd_args, dataset_name))
            
        # 智能判断模型类型并配置相应参数
        api_env = {}
        
        # 重新判断模型类型（使用修复后的model_id进行判断）
        is_local = is_local_model(model_id)  # 使用修复后的model_id而不是task.model_id
        actual_eval_type = 'llm_ckpt' if is_local else 'openai_api'
        
        reporter.log("INFO", f"🔍 模型类型判断:")
        reporter.log("INFO", f"   原始模型ID: {task.model_id}")
        reporter.log("INFO", f"   修复后模型ID: {model_id}")
        reporter.log("INFO", f"   数据库eval_type: {task.eval_type}")
        reporter.log("INFO", f"   实际判断结果: {'本地模型' if is_local else 'API模型'}")
        reporter.log("INFO", f"   使用eval_type: {actual_eval_type}")
        
        # 4.5. 记录模型使用情况（在确定最终模型ID后）
        try:
            from app.services.model_management_service import ModelManagementService
            model_service = ModelManagementService(db)
            
            # 记录模型使用情况（使用同步方法）
            usage_recorded = model_service.log_model_usage_by_name_sync(
                model_name=model_id,
                usage_type='evalscope_eval',
                task_name=task.task_name,
                user_id=task.user_id
            )
            
            if usage_recorded:
                reporter.log("INFO", f"📊 已记录模型使用情况: {model_id}")
            else:
                reporter.log("WARNING", f"⚠️ 未能记录模型使用情况: {model_id} (可能模型不在管理系统中)")
                
        except Exception as e:
            # 使用记录失败不应该影响评测任务
            reporter.log("WARNING", f"⚠️ 记录模型使用失败: {e}")
        
        if actual_eval_type == 'openai_api':
            # 调试：检查任务的extra_metadata
            reporter.log("DEBUG", f"任务ID: {task.id}")
            reporter.log("DEBUG", f"任务extra_metadata类型: {type(task.extra_metadata)}")
            reporter.log("DEBUG", f"任务extra_metadata内容: {task.extra_metadata}")
            
            # ==================== API配置初始化 ====================
            # 重要：不使用任何默认值，强制要求用户明确配置
            # 原因：避免因使用错误的默认URL导致API调用失败但难以排查
            # 问题定位：如果这里为None，后续会抛出明确的错误信息
            api_key = None
            api_url = None
            
            # ==================== 从用户配置中提取API凭证 ====================
            # 从task.extra_metadata['user_model_config']中获取API密钥和URL
            # 问题定位：查看DEBUG日志中的task.extra_metadata内容
            reporter.log("DEBUG", f"🔍 检查task.extra_metadata: {task.extra_metadata}")
            
            if hasattr(task, 'extra_metadata') and task.extra_metadata and task.extra_metadata.get('user_model_config'):
                user_config = task.extra_metadata['user_model_config']
                reporter.log("INFO", f"✅ 获取到用户模型配置: {user_config}")
                
                if user_config.get('api_key'):
                    api_key = user_config['api_key']
                    reporter.log("INFO", f"✅ 使用用户配置的API密钥: {api_key[:15]}...")
                else:
                    reporter.log("ERROR", "⚠️ 用户配置中没有API密钥！")
                
                # 提取base_url配置
                if user_config.get('base_url'):
                    api_url = user_config['base_url']
                    reporter.log("INFO", f"✅ 使用用户配置的API URL: {api_url}")
                else:
                    # base_url缺失会在后续验证中统一处理
                    reporter.log("ERROR", f"⚠️ 用户配置中没有base_url字段")
            else:
                # 问题定位：如果进入这个分支，说明task.extra_metadata中没有user_model_config
                # 解决方案：检查创建任务时是否正确保存了用户配置
                reporter.log("ERROR", "❌ 没有找到用户配置！")
                reporter.log("DEBUG", f"🔍 task.extra_metadata内容: {task.extra_metadata}")
            
            # ==================== API配置验证 ====================
            # 在实际调用API前验证必需的配置项，避免执行到一半才失败
            # 问题定位：如果抛出异常，检查【大模型管理】中的模型配置
            
            # 验证API密钥
            if not api_key:
                error_msg = "未找到有效的API密钥。请在【大模型管理】中配置正确的模型API密钥。"
                reporter.log("ERROR", error_msg)
                reporter.log("ERROR", "排查步骤: 1) 检查模型是否已添加 2) 检查API密钥字段是否填写 3) 检查任务创建时是否正确传递配置")
                raise Exception(error_msg)
            
            # 验证API URL
            if not api_url:
                error_msg = "未找到有效的API URL。请在【大模型管理】中配置正确的模型base_url。"
                reporter.log("ERROR", error_msg)
                reporter.log("ERROR", "排查步骤: 1) 检查模型配置中的base_url字段 2) 确认URL格式正确(如: https://dashscope.aliyuncs.com/compatible-mode/v1)")
                raise Exception(error_msg)
            
        # 初始化变量
        results = []
        python_api_success = False
        stdout_lines = []
        
        # 初始化环境变量（避免作用域问题）
        env = os.environ.copy()
        
        # === 性能优化：根据任务大小和配置决定执行策略 ===
        # 计算总样本数
        total_task_samples = 0
        if task.dataset_args:
            for dataset in task.datasets:
                if dataset in task.dataset_args and 'limit' in task.dataset_args[dataset]:
                    total_task_samples += task.dataset_args[dataset]['limit']
        
        # 决定是否使用Python API
        use_python_api = settings.EVALSCOPE_PREFER_PYTHON_API
        if total_task_samples > 0 and total_task_samples < settings.EVALSCOPE_SMALL_TASK_THRESHOLD:
            # 小任务：直接使用命令行（更快）
            use_python_api = False
            reporter.log("INFO", f"🚀 小任务检测（{total_task_samples}样本），使用快速执行路径（命令行模式）")
        elif not settings.EVALSCOPE_PREFER_PYTHON_API:
            reporter.log("INFO", f"🚀 配置为命令行优先模式（EVALSCOPE_PREFER_PYTHON_API=false）")
        
        # 优先使用Python API方式（更可靠，直接传递配置）
        if use_python_api:
            reporter.log("INFO", "")
            reporter.log("INFO", "=" * 80)
            reporter.log("INFO", "🚀 尝试使用 EvalScope Python API 进行评测...")
            reporter.log("INFO", "=" * 80)
            reporter.log("INFO", f"📌 模型: {model_id}")
            reporter.log("INFO", f"📌 eval_type: {actual_eval_type}")
            reporter.log("INFO", f"📌 数据集: {', '.join(task.datasets)}")
            if actual_eval_type == 'openai_api':
                reporter.log("INFO", f"📌 API URL: {api_url if 'api_url' in locals() else 'N/A'}")
                reporter.log("INFO", f"📌 API密钥: {'已配置' if 'api_key' in locals() and api_key else '未配置'}")
            reporter.log("INFO", "=" * 80)
            reporter.log("INFO", "")
        
        reporter.set_phase('loading_model')
        reporter.update_progress(15, "加载模型中")
        
        if use_python_api:
            try:
                # 导入evalscope Python API
                from evalscope.run import run_task
                from evalscope.config import TaskConfig
                
                reporter.set_phase('evaluating')
                
                # 为每个数据集单独评测（支持并行）
                def run_single_dataset(dataset_name):
                    # 更新数据集状态为运行中
                    reporter.update_dataset_progress(dataset_name, 0, 'running', '开始评测')
                    reporter.log("INFO", f"开始评测数据集: {dataset_name}")
                
                    # 确定数据集工作目录
                    dataset_work_dir = work_dir / f'dataset_{dataset_name}' if len(task.datasets) > 1 else work_dir
                    
                    config_params = {
                        'model': model_id,
                        'datasets': [dataset_name],
                        'eval_type': actual_eval_type,
                        'work_dir': str(dataset_work_dir)
                    }
                    
                    # 如果是恢复的任务，添加use_cache参数以继续执行
                    if is_resumed:
                        # 查找该数据集的最新时间戳目录
                        cache_dir = None
                        if dataset_work_dir.exists():
                            timestamp_dirs = [d for d in dataset_work_dir.iterdir() if d.is_dir() and d.name.startswith('2025')]
                            if timestamp_dirs:
                                cache_dir = max(timestamp_dirs, key=lambda x: x.name)
                        
                        if cache_dir:
                            config_params['use_cache'] = str(cache_dir)
                            reporter.log("INFO", f"🔄 [{dataset_name}] Python API 使用缓存继续执行: {cache_dir}")
                        else:
                            reporter.log("WARNING", f"⚠️ [{dataset_name}] 未找到缓存目录，将重新开始")
                
                    # 从dataset_args中获取该数据集的limit
                    total_samples = None
                    if task.dataset_args and dataset_name in task.dataset_args:
                        dataset_config = task.dataset_args[dataset_name]
                        if 'limit' in dataset_config:
                            config_params['limit'] = dataset_config['limit']
                            total_samples = dataset_config['limit']
                
                    # 初始化数据集进度信息（包含总样本数）
                    if total_samples:
                        reporter.update_dataset_progress(
                            dataset_name, 0, 'running', '初始化评测',
                            total_samples=total_samples,
                            completed_samples=0
                        )
                        reporter.log("INFO", f"📊 [{dataset_name}] 数据集样本数: {total_samples}")
                
                    # 为API模型添加配置 - TaskConfig使用api_url字段
                    if actual_eval_type == 'openai_api':
                        config_params['api_url'] = api_url  # TaskConfig字段名是api_url，内部会转换为base_url
                        config_params['api_key'] = api_key
                        reporter.log("INFO", f"✅ [{dataset_name}] 使用API配置: {api_url}")
                        reporter.log("DEBUG", f"🔍 [{dataset_name}] config_params['api_url'] = {config_params['api_url']}")
                        reporter.log("DEBUG", f"🔍 [{dataset_name}] config_params['api_key'] = {'***' if config_params['api_key'] else 'None'}")
                
                    # 添加其他参数
                    if task.model_args:
                        config_params['model_args'] = task.model_args
                    if task.generation_config:
                        config_params['generation_config'] = task.generation_config
                
                    # 输出完整配置（隐藏敏感信息）
                    config_debug = {k: ('***' if k == 'api_key' else v) for k, v in config_params.items()}
                    reporter.log("INFO", f"")
                    reporter.log("INFO", f"📋 [{dataset_name}] Python API 配置参数:")
                    for key, value in config_debug.items():
                        reporter.log("INFO", f"   • {key}: {value}")
                    reporter.log("INFO", f"")
                
                    # 创建TaskConfig
                    eval_config = TaskConfig(**config_params)
                    reporter.log("INFO", f"✅ [{dataset_name}] TaskConfig创建成功")
                    reporter.log("INFO", f"🚀 [{dataset_name}] 开始评测...")
                
                    # 获取数据集工作目录
                    dataset_work_dir = work_dir / f'dataset_{dataset_name}' if len(task.datasets) > 1 else work_dir
                
                    # 启动进度监控线程
                    import threading
                    stop_monitor = threading.Event()
                
                    def monitor_progress():
                        """监控评测进度的后台线程（智能频率调整）"""
                        last_completed = 0
                    
                        # === 性能优化：根据任务大小智能调整监控间隔 ===
                        if total_samples and total_samples < settings.EVALSCOPE_SMALL_TASK_THRESHOLD:
                            # 小任务：使用较长间隔或禁用监控
                            monitor_interval = settings.EVALSCOPE_PROGRESS_INTERVAL_SMALL
                            reporter.log("INFO", f"📊 [{dataset_name}] 小任务检测（{total_samples}样本），监控间隔: {monitor_interval}秒")
                        else:
                            # 大任务：使用较短间隔
                            monitor_interval = settings.EVALSCOPE_PROGRESS_INTERVAL_LARGE
                            reporter.log("INFO", f"📊 [{dataset_name}] 大任务检测，监控间隔: {monitor_interval}秒")
                    
                        while not stop_monitor.is_set():
                            try:
                                # 统计已完成的样本数
                                completed = count_completed_samples(dataset_work_dir)
                            
                                # 只在有变化时更新
                                if completed != last_completed:
                                    last_completed = completed
                                
                                    # 计算进度百分比
                                    if total_samples and total_samples > 0:
                                        progress = min(int(completed / total_samples * 100), 99)  # 最多99%，100%留给完成时
                                    else:
                                        progress = 0
                                
                                    # 更新进度（使用节流机制）
                                    reporter.update_dataset_progress(
                                        dataset_name,
                                        progress,
                                        'running',
                                        f'已完成 {completed}/{total_samples if total_samples else "?"}',
                                        total_samples=total_samples,
                                        completed_samples=completed
                                    )
                                    reporter.log("INFO", f"📈 [{dataset_name}] 进度更新: {completed}/{total_samples if total_samples else '?'} ({progress}%)")
                            except Exception as e:
                                reporter.log("WARNING", f"进度监控出错: {e}")
                        
                            # 使用智能监控间隔
                            time.sleep(monitor_interval)
                
                    # 启动监控线程
                    monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
                    monitor_thread.start()
                    reporter.log("INFO", f"✅ [{dataset_name}] 进度监控线程已启动")
                
                    try:
                        # 执行评测
                        result = run_task(eval_config)
                        reporter.log("INFO", f"✅ [{dataset_name}] 评测完成")
                    finally:
                        # 停止监控线程
                        stop_monitor.set()
                        monitor_thread.join(timeout=5)  # 等待最多5秒
                        reporter.log("INFO", f"✅ [{dataset_name}] 进度监控线程已停止")
                
                    return dataset_name, result
            
                # 并行处理多个数据集
                if len(task.datasets) > 1:
                    reporter.log("INFO", f"🚀 使用Python API并行处理 {len(task.datasets)} 个数据集")
                    import concurrent.futures
                
                    results = []
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(task.datasets), 3)) as executor:
                        future_to_dataset = {
                            executor.submit(run_single_dataset, dataset): dataset 
                            for dataset in task.datasets
                        }
                    
                        for future in concurrent.futures.as_completed(future_to_dataset):
                            dataset_name, result = future.result()
                            results.append(result)
                        
                            # 更新数据集完成状态
                            reporter.update_dataset_progress(dataset_name, 100, 'completed', '评测完成')
                            reporter.log("INFO", f"✅ 数据集 {dataset_name} 评测完成")
                        
                            progress = len(results) * 80 / len(task.datasets) + 15
                            reporter.update_progress(int(progress), f"完成数据集 {dataset_name}")
                else:
                    # 单个数据集
                    dataset_name, result = run_single_dataset(task.datasets[0])
                    results = [result]
                
                    # 更新数据集完成状态
                    reporter.update_dataset_progress(dataset_name, 100, 'completed', '评测完成')
                    reporter.log("INFO", f"✅ 数据集 {dataset_name} 评测完成")
            
                reporter.log("INFO", f"🎉 Python API评测成功完成！")
                reporter.set_phase('processing_results')
                reporter.update_progress(95, "处理评测结果")
            
                # Python API 成功，直接跳转到结果处理
                python_api_success = True
            
            except Exception as api_error:
                reporter.log("WARNING", "")
                reporter.log("WARNING", "⚠️  Python API执行失败，即将回退到命令行方式")
                reporter.log("WARNING", f"💥 错误原因: {api_error}")
                reporter.log("WARNING", f"🔄 回退策略: 使用命令行模式重新执行")
                reporter.log("WARNING", "")
                # 继续使用命令行方式
                results = []
                python_api_success = False
        
        # 只有Python API失败时才使用命令行方式
        if not python_api_success:
            # 为所有数据集命令添加工作目录参数和API参数
            for i, (dataset_name, cmd_args) in enumerate(dataset_commands):
                # 为每个数据集使用独立的工作目录
                dataset_work_dir = work_dir / f'dataset_{dataset_name}' if len(task.datasets) > 1 else work_dir
                cmd_args.extend(['--work-dir', str(dataset_work_dir)])
                
                # 如果是恢复的任务，添加use-cache参数以继续执行
                if is_resumed:
                    # 查找该数据集的最新时间戳目录
                    cache_dir = None
                    if dataset_work_dir.exists():
                        timestamp_dirs = [d for d in dataset_work_dir.iterdir() if d.is_dir() and d.name.startswith('2025')]
                        if timestamp_dirs:
                            cache_dir = max(timestamp_dirs, key=lambda x: x.name)
                    
                    if cache_dir:
                        cmd_args.extend(['--use-cache', str(cache_dir)])
                        reporter.log("INFO", f"🔄 [{dataset_name}] 命令行使用缓存继续执行: {cache_dir}")
                    else:
                        reporter.log("WARNING", f"⚠️ [{dataset_name}] 未找到缓存目录，将重新开始")
                
                # 添加eval_type参数（关键：告诉EvalScope使用哪种评测方式）
                cmd_args.extend(['--eval-type', actual_eval_type])
                
                # 为API模型添加认证参数
                if actual_eval_type == 'openai_api':
                    if 'api_key' in locals() and 'api_url' in locals():
                        cmd_args.extend(['--api-key', api_key])
                        cmd_args.extend(['--api-url', api_url])  # evalscope命令行参数使用--api-url
                        reporter.log("DEBUG", f"为命令行添加API参数: api_url={api_url}")
                    else:
                        reporter.log("ERROR", "命令行模式需要API配置，但未定义api_key或api_url")
                
                dataset_commands[i] = (dataset_name, cmd_args)
        
            # 调试：显示最终的命令行参数并保存到文件
            reporter.log("INFO", "=" * 80)
            reporter.log("INFO", f"🚀 准备执行 {len(dataset_commands)} 个评测命令")
            reporter.log("INFO", "=" * 80)
            for dataset_name, cmd_args in dataset_commands:
                cmd_str = ' '.join(cmd_args)
                reporter.log("INFO", f"📌 数据集: {dataset_name}")
                reporter.log("INFO", f"📋 命令: {cmd_str}")
                reporter.log("INFO", "-" * 80)
            
            # 将命令保存到文件供调试
            debug_cmd_file = work_dir / 'debug_command.sh'
            try:
                with open(debug_cmd_file, 'w') as f:
                    f.write("#!/bin/bash\n")
                    f.write("# 自动生成的EvalScope评测命令\n\n")
                    f.write(f"# 任务ID: {task_id}\n")
                    f.write(f"# 生成时间: {datetime.now(timezone.utc)}\n")
                    f.write(f"# 数据集数量: {len(dataset_commands)}\n\n")
                    
                    for dataset_name, cmd_args in dataset_commands:
                        cmd_str = ' '.join(cmd_args)
                        f.write(f"# 数据集: {dataset_name}\n")
                        f.write(cmd_str + "\n\n")
                reporter.log("INFO", f"📝 命令已保存到: {debug_cmd_file}")
            except Exception as e:
                reporter.log("WARNING", f"保存命令文件失败: {e}")
            
            reporter.update_progress(15, "准备评测命令")
        
            # 5. 执行evalscope命令 - 支持并行处理
            reporter.log("INFO", "开始执行EvalScope评测...")
            
            # 打印可以直接复制执行的命令（格式化为多行便于阅读）
            reporter.log("INFO", "")
            reporter.log("INFO", "💡 可复制到终端测试的命令格式:")
            reporter.log("INFO", "=" * 80)
            for dataset_name, cmd_args in dataset_commands:
                printable_cmd = ' \\\n  '.join(cmd_args)
                reporter.log("INFO", f"# 数据集: {dataset_name}")
                reporter.log("INFO", printable_cmd)
                reporter.log("INFO", "")
            reporter.log("INFO", "=" * 80)
            
            # 6. 执行evalscope命令 - 支持并行处理
            if len(dataset_commands) > 1:
                # 多数据集并行处理
                reporter.log("INFO", f"🚀 开始并行执行 {len(dataset_commands)} 个数据集评测")
            
            def run_dataset_command(dataset_name, cmd_args):
                """运行单个数据集的命令"""
                reporter.log("INFO", "")
                reporter.log("INFO", f"▶️  [{dataset_name}] 开始执行命令行评测")
                reporter.log("INFO", f"📋 执行命令: {' '.join(cmd_args)}")
                reporter.log("INFO", "")
                process = subprocess.Popen(
                    cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    env=env
                )
                
                # 保存进程信息到进程管理器
                try:
                    process_manager = ProcessManager(task_id)
                    process_manager.save_process_info(dataset_name, process.pid, cmd_args)
                    reporter.log("INFO", f"💾 保存进程信息: {dataset_name} -> PID {process.pid}")
                except Exception as e:
                    reporter.log("WARNING", f"保存进程信息失败: {e}")
                
                stdout_lines = []
                stderr_lines = []
                
                while True:
                    if process.poll() is not None:
                        remaining_stdout = process.stdout.read()
                        remaining_stderr = process.stderr.read()
                        if remaining_stdout:
                            stdout_lines.extend(remaining_stdout.strip().split('\n'))
                        if remaining_stderr:
                            stderr_lines.extend(remaining_stderr.strip().split('\n'))
                        break
                    
                    try:
                        output = process.stdout.readline()
                        if output:
                            line = output.strip()
                            stdout_lines.append(line)
                            reporter.log("INFO", f"[{dataset_name}] {line}")
                    except Exception as e:
                        reporter.log("WARNING", f"[{dataset_name}] 读取输出错误: {e}")
                        time.sleep(0.1)
                
                return_code = process.returncode
                if return_code != 0:
                    error_output = '\n'.join(stderr_lines[-10:])
                    cmd_str = ' '.join(cmd_args)
                    reporter.log("ERROR", "")
                    reporter.log("ERROR", f"❌ [{dataset_name}] EvalScope执行失败")
                    reporter.log("ERROR", f"📋 执行的命令: {cmd_str}")
                    reporter.log("ERROR", f"🔢 返回码: {return_code}")
                    reporter.log("ERROR", f"⚠️  错误输出（最后10行）:")
                    for err_line in stderr_lines[-10:]:
                        reporter.log("ERROR", f"   {err_line}")
                    reporter.log("ERROR", "")
                    error_msg = f"[{dataset_name}] EvalScope执行失败 (返回码: {return_code})\n错误输出:\n{error_output}"
                    raise Exception(error_msg)
                
                reporter.log("INFO", f"[{dataset_name}] 执行完成")
                return dataset_name, stdout_lines, stderr_lines
            
            # 并行执行所有数据集
            import concurrent.futures
            stdout_lines = []
            stderr_lines = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(dataset_commands), 3)) as executor:
                # 提交所有任务
                future_to_dataset = {
                    executor.submit(run_dataset_command, dataset_name, cmd_args): dataset_name 
                    for dataset_name, cmd_args in dataset_commands
                }
                
                # 收集结果
                for future in concurrent.futures.as_completed(future_to_dataset):
                    dataset_name = future_to_dataset[future]
                    try:
                        dataset_name, dataset_stdout, dataset_stderr = future.result()
                        stdout_lines.extend(dataset_stdout)
                        stderr_lines.extend(dataset_stderr)
                        reporter.log("INFO", f"✅ 数据集 {dataset_name} 评测完成")
                    except Exception as exc:
                        reporter.log("ERROR", f"❌ 数据集 {dataset_name} 评测失败: {exc}")
                        raise exc
            
            reporter.log("INFO", f"🎉 所有 {len(dataset_commands)} 个数据集并行评测完成")
        else:
            # 单个数据集，使用原有逻辑
            dataset_name, cmd_args = dataset_commands[0]
            reporter.log("INFO", "")
            reporter.log("INFO", f"🚀 开始执行单个数据集评测: {dataset_name}")
            reporter.log("INFO", f"📋 执行命令: {' '.join(cmd_args)}")
            reporter.log("INFO", "")
            
            process = subprocess.Popen(
                cmd_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env
            )
            
            # 保存进程信息到进程管理器
            try:
                process_manager = ProcessManager(task_id)
                dataset_name = task.datasets[0] if task.datasets else "single_dataset"
                process_manager.save_process_info(dataset_name, process.pid, cmd_args)
                reporter.log("INFO", f"💾 保存进程信息: {dataset_name} -> PID {process.pid}")
            except Exception as e:
                reporter.log("WARNING", f"保存进程信息失败: {e}")
            
            reporter.update_progress(20, "EvalScope已启动")
            
            # 实时监控执行过程
            stdout_lines = []
            stderr_lines = []
            
            while True:
                if process.poll() is not None:
                    remaining_stdout = process.stdout.read()
                    remaining_stderr = process.stderr.read()
                    if remaining_stdout:
                        stdout_lines.extend(remaining_stdout.strip().split('\n'))
                    if remaining_stderr:
                        stderr_lines.extend(remaining_stderr.strip().split('\n'))
                    break
                
                try:
                    output = process.stdout.readline()
                    if output:
                        line = output.strip()
                        stdout_lines.append(line)
                        reporter.log("INFO", line)
                        
                        # 根据输出智能更新进度
                        if 'Loading model' in line or 'loading model' in line.lower():
                            reporter.update_progress(30, "加载模型中")
                        elif 'Starting evaluation' in line or 'start' in line.lower():
                            reporter.update_progress(40, "开始评测")
                        elif 'Evaluating' in line or 'evaluating' in line.lower():
                            reporter.update_progress(60, "评测进行中")
                        elif 'Finished' in line or 'completed' in line.lower():
                            reporter.update_progress(90, "评测完成")
                        elif 'Overall report' in line:
                            reporter.update_progress(95, "生成报告")
                    
                except Exception as e:
                    reporter.log("WARNING", f"读取输出错误: {e}")
                    time.sleep(0.1)
            
            # 检查返回码
            return_code = process.returncode
            if return_code != 0:
                error_output = '\n'.join(stderr_lines[-10:])
                cmd_str = ' '.join(cmd_args)
                reporter.log("ERROR", "")
                reporter.log("ERROR", f"❌ EvalScope执行失败")
                reporter.log("ERROR", f"📋 执行的命令: {cmd_str}")
                reporter.log("ERROR", f"🔢 返回码: {return_code}")
                reporter.log("ERROR", f"⚠️  错误输出（最后10行）:")
                for err_line in stderr_lines[-10:]:
                    reporter.log("ERROR", f"   {err_line}")
                reporter.log("ERROR", "")
                error_msg = f"EvalScope执行失败 (返回码: {return_code})\n错误输出:\n{error_output}"
                raise Exception(error_msg)
        
            reporter.log("INFO", "EvalScope执行成功，开始解析结果")
            reporter.update_progress(95, "解析评测结果")
            
            # 7. 解析和保存结果
            results = parse_evalscope_output(stdout_lines, task_id)
        
        # 处理评测结果（无论是Python API还是命令行方式）
        if python_api_success:
            # Python API方式的结果已经在results中了，无需进一步解析
            reporter.log("INFO", f"Python API获得 {len(results)} 个结果")
            # 对于Python API，我们需要转换结果格式
            converted_results = []
            for result in results:
                # 这里需要根据实际的result结构来转换
                # 暂时创建一个简单的结果结构
                converted_results.append({
                    'benchmark': task.datasets[0] if task.datasets else 'unknown',
                    'metric_name': 'accuracy',
                    'metric_value': 0.0,  # 这里应该从result中提取实际值
                    'category': 'default',
                    'subset_name': 'main',
                    'num_samples': 100
                })
            results = converted_results
        else:
            # 命令行方式需要解析输出
            if 'stdout_lines' in locals():
                results = parse_evalscope_output(stdout_lines, task_id)
            else:
                results = []
        
        if results:
            reporter.log("INFO", f"找到 {len(results)} 个评测结果")
            for result_data in results:
                eval_result = EvalScopeResult(
                    task_id=task_id,
                    benchmark=result_data['benchmark'],
                    metric_name=result_data['metric_name'],
                    metric_value=result_data['metric_value'],
                    category=result_data.get('category', 'default'),
                    subset_name=result_data.get('subset_name', 'main'),
                    num_samples=result_data.get('num_samples'),
                    raw_results=result_data
                )
                db.add(eval_result)
        else:
            # 如果解析失败，创建一个默认结果
            reporter.log("WARNING", "未能解析标准结果，创建默认结果")
            for dataset in task.datasets:
                eval_result = EvalScopeResult(
                    task_id=task_id,
                    benchmark=dataset,
                    metric_name='Accuracy',
                    metric_value=None,
                    category='default',
                    subset_name='main',
                    num_samples=None,
                    raw_results={'note': '评测完成但结果解析失败', 'stdout_length': len(stdout_lines)}
                )
                db.add(eval_result)
        
        # 8. 更新任务状态为完成
        task.status = 'completed'
        task.progress = 100
        task.completed_at = datetime.now()
        db.commit()
        
        reporter.set_phase('completed')
        reporter.update_progress(100, "任务完成！")
        reporter.log("SUCCESS", f"任务 {task_id} 执行成功完成")
        
        return {
            "status": "success", 
            "task_id": task_id, 
            "work_dir": str(work_dir),
            "results_count": len(results)
        }
        
    except Exception as e:
        # 错误处理
        error_msg = str(e)
        reporter.log("ERROR", f"任务执行失败: {error_msg}")
        
        if 'task' in locals():
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = datetime.now()
            db.commit()
        
        raise
        
    finally:
        db.close()


# 如果Celery不可用，提供错误提示（非模拟，所有代码均使用真实数据）
if not CELERY_AVAILABLE:
    class MockTask:
        """Celery不可用时的占位类，仅用于提供明确的错误提示"""
        def delay(self, *args, **kwargs):
            raise RuntimeError("Celery未安装或不可用。请安装: pip install celery[redis]")
    
    run_real_evaluation_task = MockTask()
    celery_app = None  # 确保celery_app被定义


__all__ = ['run_real_evaluation_task', 'celery_app', 'CELERY_AVAILABLE']
