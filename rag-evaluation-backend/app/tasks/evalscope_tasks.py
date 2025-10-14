"""
EvalScope真实评测异步任务 - 统一版本
- 合并优化版本和原版本的所有功能
- 优先使用Python API，失败时回退到命令行
- 支持RAGEval后端评测
- 增强错误处理和进度跟踪
"""
import os
import sys
import subprocess
import json
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

# 导入性能配置
from app.core.config import settings
from app.core.process_manager import ProcessManager

# Celery配置
try:
    from celery import Celery
    
    # ==================== Celery配置 ====================
    # 使用默认配置，Worker进程启动时已设置环境变量
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    backend_url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    
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

from app.utils.evalscope_adapter import EvalScopeAPIAdapter

logger = logging.getLogger(__name__)


def get_db_session():
    """获取数据库会话"""
    from app.models import user, evalscope_task
    from app.db.base import SessionLocal
    return SessionLocal()


def is_local_model(model_id: str) -> bool:
    """判断是否为本地模型"""
    if not model_id:
        return False
    
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


class EnhancedProgressReporter:
    """增强的进度报告器 - 基于实际样本数计算进度"""
    
    def __init__(self, db, task_id: int):
        self.db = db
        self.task_id = task_id
        self.dataset_progress = {}
        self.subset_progress = {}  # 新增：子集进度追踪
        self.current_phase = 'initializing'
        self.total_datasets = 0
        self.completed_datasets = 0
        self.logger = logging.getLogger(f"Task-{task_id}")
        self.monitoring_thread = None  # 监控线程
        self.monitoring_active = False  # 监控状态
        
        # 性能优化：节流控制
        self.last_db_update = 0  # 上次数据库更新时间
        self.last_progress = 0   # 上次进度值
        self.pending_update = None  # 待更新的数据（节流期间暂存）
    
    def initialize_datasets(self, datasets: list, dataset_args: Dict = None):
        """初始化数据集进度追踪"""
        self.total_datasets = len(datasets)
        
        for dataset in datasets:
            # 尝试获取数据集的预期样本数
            limit = None
            if dataset_args and dataset in dataset_args:
                limit = dataset_args[dataset].get('limit')
            
            self.dataset_progress[dataset] = {
                'name': dataset,
                'status': 'waiting',
                'progress': 0,
                'current_step': None,
                'total_samples': limit,  # 预期样本数
                'completed_samples': 0,
                'start_time': None,
                'end_time': None
            }
    
    def update_dataset_progress(
        self, 
        dataset_name: str, 
        completed_samples: int = None,
        total_samples: int = None,
        status: str = None,
        current_step: str = None
    ):
        """更新特定数据集的进度"""
        if dataset_name not in self.dataset_progress:
            return
        
        dataset_info = self.dataset_progress[dataset_name]
        
        # 更新样本数
        if total_samples is not None:
            dataset_info['total_samples'] = total_samples
        if completed_samples is not None:
            dataset_info['completed_samples'] = completed_samples
        
        # 计算进度
        if dataset_info['total_samples'] and dataset_info['total_samples'] > 0:
            dataset_info['progress'] = min(
                int(dataset_info['completed_samples'] / dataset_info['total_samples'] * 100),
                100
            )
        
        # 更新状态
        if status:
            dataset_info['status'] = status
            if status == 'running' and not dataset_info['start_time']:
                dataset_info['start_time'] = datetime.now(timezone.utc).isoformat()
            elif status == 'completed' and not dataset_info['end_time']:
                dataset_info['end_time'] = datetime.now(timezone.utc).isoformat()
                dataset_info['progress'] = 100
        
        if current_step:
            dataset_info['current_step'] = current_step
    
    def set_phase(self, phase: str):
        """设置当前执行阶段"""
        self.current_phase = phase
        self.logger.info(f"进入阶段: {phase}")
    
    def get_detailed_progress(self):
        """获取详细进度信息"""
        completed_count = sum(
            1 for ds in self.dataset_progress.values() 
            if ds['status'] == 'completed'
        )
        
        return {
            'overall_progress': self._calculate_overall_progress(),
            'current_dataset': self._get_current_dataset(),
            'total_datasets': self.total_datasets,
            'completed_datasets': completed_count,
            'dataset_progress': list(self.dataset_progress.values()),
            'subset_progress': list(self.subset_progress.values()),  # 新增：子集进度
            'phase': self.current_phase
        }
    
    def _calculate_overall_progress(self) -> int:
        """计算整体进度 - 基于实际评测进度"""
        if not self.dataset_progress:
            return 0
        
        # 阶段基础进度
        phase_base = {
            'initializing': 0,
            'loading_model': 5,
            'evaluating': 10,
            'processing_results': 95,
            'completed': 100
        }
        base_progress = phase_base.get(self.current_phase, 0)
        
        # 评测阶段 (10-95%)，基于数据集实际进度
        if self.current_phase == 'evaluating' and self.dataset_progress:
            # 计算所有数据集的平均进度
            dataset_avg_progress = sum(
                ds['progress'] for ds in self.dataset_progress.values()
            ) / len(self.dataset_progress)
            
            # 映射到10-95%区间
            eval_progress = 10 + (dataset_avg_progress * 0.85)
            return min(int(eval_progress), 95)
        
        return base_progress
    
    def _get_current_dataset(self) -> Optional[str]:
        """获取当前正在执行的数据集"""
        for ds in self.dataset_progress.values():
            if ds['status'] == 'running':
                return ds['name']
        return None
    
    def update_progress(self, progress: int = None, message: str = "", force: bool = False):
        """更新进度到数据库和WebSocket（带智能节流优化）"""
        from app.models.evalscope_task import EvalScopeTask
        
        # 计算整体进度
        overall_progress = self._calculate_overall_progress() if progress is None else progress
        
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
            self.pending_update = (overall_progress, message)
            if message:
                print(f"[Task {self.task_id}] {overall_progress}% - {message} (节流中)")
            return
        
        # === 执行数据库更新 ===
        task = self.db.query(EvalScopeTask).filter(
            EvalScopeTask.id == self.task_id
        ).first()
        
        if task:
            task.progress = min(overall_progress, 100)
            
            # 存储详细进度
            detailed_progress = self.get_detailed_progress()
            if message:
                detailed_progress['message'] = message
            
            if not task.extra_metadata:
                task.extra_metadata = {}
            task.extra_metadata['detailed_progress_metadata'] = detailed_progress
            
            self.db.commit()
            
            if message:
                self.logger.info(f"{overall_progress}% - {message}")
            
            # 更新节流状态
            self.last_db_update = current_time
            self.last_progress = overall_progress
            self.pending_update = None
            
            # 发送WebSocket消息
            self._send_websocket_update(overall_progress, message, detailed_progress)
    
    def _send_websocket_update(self, progress: int, message: str, detailed_progress: Dict):
        """发送WebSocket更新"""
        try:
            import asyncio
            from app.tasks.evalscope_tasks import send_progress_update
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(send_progress_update(
                        self.task_id, progress, message, detailed_progress
                    ))
                else:
                    loop.run_until_complete(send_progress_update(
                        self.task_id, progress, message, detailed_progress
                    ))
            except RuntimeError:
                asyncio.run(send_progress_update(
                    self.task_id, progress, message, detailed_progress
                ))
        except Exception as e:
            self.logger.warning(f"WebSocket发送失败: {e}")
    
    def log(self, level: str, message: str):
        """记录日志"""
        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(message)
    
    def start_progress_monitoring(self, work_dir: Path):
        """启动进度监控线程"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
            
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitor_prediction_files,
            args=(work_dir,),
            daemon=True
        )
        self.monitoring_thread.start()
        self.logger.info("🚀 启动预测文件进度监控")
        
    def stop_progress_monitoring(self):
        """停止进度监控"""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=1)
        self.logger.info("⏹️ 停止预测文件进度监控")
        
    def _monitor_prediction_files(self, work_dir: Path):
        """监控预测文件生成进度"""
        predictions_dir = work_dir / "predictions"
        
        while self.monitoring_active:
            try:
                if predictions_dir.exists():
                    self._update_subset_progress_from_files(predictions_dir)
                time.sleep(5)  # 每5秒检查一次
            except Exception as e:
                self.logger.warning(f"进度监控错误: {e}")
                break
                
    def _update_subset_progress_from_files(self, predictions_dir: Path):
        """从预测文件更新子集进度"""
        try:
            for jsonl_file in predictions_dir.glob("**/*.jsonl"):
                # 解析文件名获取子集信息
                subset_name = self._extract_subset_name(jsonl_file)
                
                # 统计文件行数
                try:
                    with open(jsonl_file, 'r', encoding='utf-8') as f:
                        completed_samples = sum(1 for _ in f)
                except Exception:
                    completed_samples = 0
                    
                # 更新子集进度
                self.update_subset_progress(subset_name, completed_samples)
                
        except Exception as e:
            self.logger.warning(f"更新子集进度失败: {e}")
            
    def _extract_subset_name(self, file_path: Path) -> str:
        """从文件路径提取子集名称"""
        # 例如: predictions/qwen3-max-2025-09-23/mmlu_abstract_algebra.jsonl
        # 提取: abstract_algebra
        filename = file_path.stem  # mmlu_abstract_algebra
        if '_' in filename:
            return filename.split('_', 1)[1]  # abstract_algebra
        return filename
        
    def update_subset_progress(self, subset_name: str, completed_samples: int, total_samples: int = None):
        """更新子集进度"""
        if subset_name not in self.subset_progress:
            self.subset_progress[subset_name] = {
                'name': subset_name,
                'completed': 0,
                'total': total_samples or 0,
                'progress': 0,
                'status': 'waiting',
                'last_updated': None
            }
            
        subset_info = self.subset_progress[subset_name]
        old_completed = subset_info['completed']
        subset_info['completed'] = completed_samples
        subset_info['last_updated'] = datetime.now(timezone.utc).isoformat()
        
        if subset_info['total'] > 0:
            subset_info['progress'] = min(int(completed_samples / subset_info['total'] * 100), 100)
        else:
            # 如果没有总数，根据文件是否完整判断
            subset_info['progress'] = 100 if completed_samples > 0 else 0
            
        subset_info['status'] = 'completed' if subset_info['progress'] == 100 else 'running'
        
        # 如果进度有变化，更新整体进度
        if completed_samples != old_completed:
            self.update_progress(message=f"子集 {subset_name}: {completed_samples} 样本完成")
            
    def get_current_subset(self) -> Optional[str]:
        """获取当前正在处理的子集"""
        for subset in self.subset_progress.values():
            if subset['status'] == 'running':
                return subset['name']
        return None


class ResultParser:
    """结果解析器 - 从EvalScope返回结果中提取信息"""
    
    @staticmethod
    def parse_evalscope_result(result: Dict, dataset_name: str) -> List[Dict]:
        """
        解析EvalScope返回的结果
    
    Args:
            result: run_task()返回的结果字典
            dataset_name: 数据集名称
            
        Returns:
            标准化的结果列表
        """
        parsed_results = []
        
        try:
            # EvalScope返回的结果结构: {dataset_name: Report对象}
            if isinstance(result, dict) and dataset_name in result:
                report = result[dataset_name]
                
                # 检查Report对象是否有metrics属性
                if hasattr(report, 'metrics') and report.metrics:
                    for metric in report.metrics:
                        metric_name = getattr(metric, 'name', 'unknown')
                        metric_score = getattr(metric, 'score', 0.0)
                        metric_num = getattr(metric, 'num', 0)
                        
                        # 处理类别和子集
                        if hasattr(metric, 'categories') and metric.categories:
                            for category in metric.categories:
                                category_name = getattr(category, 'name', ['default'])
                                if isinstance(category_name, list):
                                    category_name = category_name[0] if category_name else 'default'
                                
                                # 处理子集
                                if hasattr(category, 'subsets') and category.subsets:
                                    for subset in category.subsets:
                                        subset_name = getattr(subset, 'name', 'main')
                                        subset_score = getattr(subset, 'score', metric_score)
                                        subset_num = getattr(subset, 'num', metric_num)
                                        
                                        parsed_results.append({
                                            'benchmark': dataset_name,
                                            'metric_name': metric_name,
                                            'metric_value': float(subset_score),
                                            'category': category_name,
                                            'subset_name': subset_name,
                                            'num_samples': subset_num
                                        })
                                else:
                                    # 没有子集，使用类别级别的数据
                                    parsed_results.append({
                                        'benchmark': dataset_name,
                                        'metric_name': metric_name,
                                        'metric_value': float(metric_score),
                                        'category': category_name,
                                        'subset_name': 'main',
                                        'num_samples': metric_num
                                    })
                        else:
                            # 没有类别，使用指标级别的数据
                            parsed_results.append({
                                'benchmark': dataset_name,
                                'metric_name': metric_name,
                                'metric_value': float(metric_score),
                                'category': 'default',
                                'subset_name': 'main',
                                'num_samples': metric_num
                            })
                
                # 如果没有metrics属性，尝试从Report对象直接提取
                elif hasattr(report, 'score'):
                    parsed_results.append({
                        'benchmark': dataset_name,
                        'metric_name': 'overall_score',
                        'metric_value': float(getattr(report, 'score', 0.0)),
                        'category': 'default',
                        'subset_name': 'main',
                        'num_samples': getattr(report, 'num_samples', None)
                    })
            
            # 如果无法解析，返回空列表
            if not parsed_results:
                logger.warning(f"无法解析数据集 {dataset_name} 的结果: {result}")
                
        except Exception as e:
            logger.error(f"解析结果时出错: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
        
        return parsed_results
    
    @staticmethod
    def load_results_from_json_files(work_dir: Path) -> List[Dict]:
        """
        从工作目录的JSON文件中加载结果
        
        Args:
            work_dir: 工作目录路径
            
        Returns:
            标准化的结果列表
        """
        results = []
        
        try:
            # 查找所有JSON报告文件
            json_files = list(work_dir.glob("**/reports/*/*.json"))
            logger.info(f"找到 {len(json_files)} 个JSON结果文件")
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        report_data = json.load(f)
                    
                    # 提取结果
                    dataset_name = report_data.get('dataset_name', 'unknown')
                    
                    if 'metrics' in report_data:
                        for metric in report_data['metrics']:
                            # 处理带子集的指标
                            if 'categories' in metric:
                                for category in metric['categories']:
                                    if 'subsets' in category:
                                        # 为每个子集单独创建结果记录
                                        for subset in category['subsets']:
                                            subset_score = subset.get('score', 0)
                                            subset_samples = subset.get('num', 0)
                                            
                                            results.append({
                                                'benchmark': dataset_name,
                                                'metric_name': metric.get('name', 'accuracy'),
                                                'metric_value': subset_score,
                                                'category': category.get('name', 'default'),
                                                'subset_name': subset.get('name', 'unknown'),
                                                'num_samples': subset_samples
                                            })
                                        
                                        # 同时添加加权平均结果
                                        total_samples = 0
                                        weighted_score = 0
                                        
                                        for subset in category['subsets']:
                                            subset_score = subset.get('score', 0)
                                            subset_samples = subset.get('num', 0)
                                            weighted_score += subset_score * subset_samples
                                            total_samples += subset_samples
                                        
                                        if total_samples > 0:
                                            avg_score = weighted_score / total_samples
                                            results.append({
                                                'benchmark': dataset_name,
                                                'metric_name': metric.get('name', 'accuracy'),
                                                'metric_value': avg_score,
                                                'category': category.get('name', 'default'),
                                                'subset_name': 'average',
                                                'num_samples': total_samples
                                            })
                            else:
                                # 简单指标
                                results.append({
                                    'benchmark': dataset_name,
                                    'metric_name': metric.get('name', 'accuracy'),
                                    'metric_value': metric.get('score', 0),
                                    'category': 'default',
                                    'subset_name': 'main',
                                    'num_samples': metric.get('num', 0)
                                })
                
                except Exception as e:
                    logger.error(f"解析JSON文件 {json_file} 失败: {e}")
        
        except Exception as e:
            logger.error(f"加载JSON结果文件失败: {e}")
        
        return results


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
    """执行真实的EvalScope评测任务 - 统一版本"""
    from app.models.evalscope_task import EvalScopeTask, EvalScopeResult
    
    db = get_db_session()
    reporter = EnhancedProgressReporter(db, task_id)
    
    try:
        # 1. 获取任务
        task = db.query(EvalScopeTask).filter(
            EvalScopeTask.id == task_id
        ).first()
        
        if not task:
            raise Exception(f"任务 {task_id} 不存在")
        
        # 存储Celery任务ID到数据库
        if not task.extra_metadata:
            task.extra_metadata = {}
        task.extra_metadata['celery_task_id'] = self.request.id
        db.commit()
        
        # 输出任务概览
        reporter.log("INFO", "=" * 80)
        reporter.log("INFO", f"🎯 开始执行评测任务")
        reporter.log("INFO", "=" * 80)
        reporter.log("INFO", f"📝 任务名称: {task.task_name}")
        reporter.log("INFO", f"🆔 任务ID: {task_id}")
        reporter.log("INFO", f"🤖 模型: {task.model_id}")
        reporter.log("INFO", f"📊 数据集: {', '.join(task.datasets)}")
        reporter.log("INFO", f"🔧 评测类型: {task.eval_type}")
        reporter.log("INFO", "=" * 80)
        
        # 2. 更新状态
        task.status = 'running'
        task.started_at = datetime.now()
        db.commit()
        
        reporter.set_phase('initializing')
        reporter.initialize_datasets(task.datasets, task.dataset_args)
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
        
        # 检查任务恢复状态 - 强制拆分目录结构
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
        
        # 启动进度监控
        reporter.start_progress_monitoring(work_dir)
        
        # 初始化进程管理器
        process_manager = ProcessManager(task_id)
        
        # 4. 解析模型配置（任务创建时已经解析，这里直接使用）
        model_name = task.model_id
        eval_type = task.eval_type
        
        # 提取API配置
        api_config = None
        if eval_type == 'openai_api':
            api_config = EvalScopeAPIAdapter.extract_api_config_from_metadata(
                task.extra_metadata
            )
            
            if not EvalScopeAPIAdapter.validate_api_config(api_config):
                raise ValueError(
                    "API模型缺少有效的API配置。请在【大模型管理】中配置模型API密钥。"
                )
            
            reporter.log("INFO", f"✅ API配置已加载: {api_config.get('api_url', 'N/A')}")
        
        reporter.log("INFO", f"✅ 模型配置:")
        reporter.log("INFO", f"   模型名: {model_name}")
        reporter.log("INFO", f"   评测类型: {eval_type}")
        
        # 5. 记录模型使用情况
        try:
            from app.services.model_management_service import ModelManagementService
            model_service = ModelManagementService(db)
            
            usage_recorded = model_service.log_model_usage_by_name_sync(
                model_name=model_name,
                usage_type='evalscope_eval',
                task_name=task.task_name,
                user_id=task.user_id
            )
            
            if usage_recorded:
                reporter.log("INFO", f"📊 已记录模型使用情况")
        except Exception as e:
            reporter.log("WARNING", f"⚠️ 记录模型使用失败: {e}")
        
        reporter.set_phase('loading_model')
        reporter.update_progress(10, "准备评测环境")
        
        # 6. 根据评测后端选择执行方式
        reporter.log("INFO", "")
        reporter.log("INFO", "=" * 80)
        
        if task.eval_backend == 'RAGEval':
            reporter.log("INFO", "🚀 使用 RAGEval 评测后端进行RAG评测")
            reporter.log("INFO", "=" * 80)
            
            # 使用RAGEval后端进行RAG评测
            try:
                from app.services.rageval_evaluator import RAGEvalEvaluator
                
                reporter.set_phase('evaluating')
                reporter.update_progress(15, "开始RAG评测")
                
                # 创建RAGEval评测器
                rageval_evaluator = RAGEvalEvaluator(
                    db=db,
                    task=task,
                    work_dir=work_dir,
                    reporter=reporter,
                    process_manager=process_manager
                )
                
                # 执行RAG评测
                all_results = rageval_evaluator.evaluate()
                
            except Exception as e:
                logger.error(f"RAGEval评测失败: {e}")
                reporter.log("ERROR", f"❌ RAGEval评测失败: {e}")
                raise
                
        else:
            # Native 和 EvalScope 后端都使用 EvalScope Python API
            backend_name = "Native" if task.eval_backend == 'Native' else "EvalScope"
            reporter.log("INFO", f"🚀 使用 {backend_name} 评测后端进行评测")
            reporter.log("INFO", "=" * 80)
            
            # 优先使用Python API方式（更可靠，直接传递配置）
            python_api_success = False
            all_results = []
            
            try:
                # ⚠️ 重要：必须在导入evalscope之前设置，避免多线程并行时的tqdm锁冲突
                os.environ['TQDM_DISABLE'] = '1'
                
                from evalscope.run import run_task
                from evalscope.config import TaskConfig
                
                reporter.set_phase('evaluating')
                reporter.update_progress(15, "开始评测")
                
                # 为每个数据集单独评测 - 支持并行处理
                def run_single_dataset(dataset_name):
                    """运行单个数据集的评测"""
                    # 检查任务是否被取消
                    if getattr(self.request, 'cancelled', False):
                        reporter.log("WARNING", f"⚠️ 任务已被取消，停止执行")
                        return {"status": "cancelled", "message": "任务已被取消"}
                    
                    reporter.log("INFO", f"")
                    reporter.log("INFO", f"▶️  评测数据集: {dataset_name}")
                    reporter.update_dataset_progress(dataset_name, status='running', current_step='准备')
                    
                    # 确定数据集工作目录 - 强制拆分目录
                    # 每个数据集必须有独立的目录，EvalScope会在该目录下创建时间戳目录
                    dataset_work_dir = work_dir / dataset_name
                    dataset_work_dir.mkdir(parents=True, exist_ok=True)
                    reporter.log("INFO", f"🔧 [{dataset_name}] 创建独立工作目录: {dataset_work_dir}")
                    
                    # 如果是恢复的任务，查找缓存目录
                    cache_dir = None
                    if is_resumed:
                        if dataset_work_dir.exists():
                            timestamp_dirs = [d for d in dataset_work_dir.iterdir() if d.is_dir() and d.name.startswith('2025')]
                            if timestamp_dirs:
                                cache_dir = max(timestamp_dirs, key=lambda x: x.name)
                    
                    # 构建TaskConfig参数
                    config_params = EvalScopeAPIAdapter.build_task_config_params(
                        model_name=model_name,
                        datasets=[dataset_name],
                        eval_type=eval_type,
                        work_dir=str(dataset_work_dir),
                        api_config=api_config,
                        model_args=task.model_args,
                        generation_config=task.generation_config,
                        dataset_args=task.dataset_args,
                        limit=task.dataset_args.get(dataset_name, {}).get('limit') if task.dataset_args else None,
                        use_cache=str(cache_dir) if is_resumed and cache_dir else None  # 恢复时使用缓存
                    )
                    
                    # 如果是恢复的任务，记录日志
                    if is_resumed:
                        if cache_dir:
                            reporter.log("INFO", f"🔄 [{dataset_name}] 优化版任务使用缓存继续执行: {cache_dir}")
                        else:
                            reporter.log("WARNING", f"⚠️ [{dataset_name}] 未找到缓存目录，将重新开始")
                    
                    # 输出配置（隐藏敏感信息）
                    config_debug = {k: ('***' if k == 'api_key' else v) for k, v in config_params.items()}
                    reporter.log("INFO", f"📋 配置参数:")
                    for key, value in config_debug.items():
                        reporter.log("INFO", f"   • {key}: {value}")
                    
                    # 创建TaskConfig并执行
                    eval_config = TaskConfig(**config_params)
                    reporter.log("INFO", f"🚀 开始评测...")
                    
                    # 执行评测前再次检查取消状态
                    if getattr(self.request, 'cancelled', False):
                        reporter.log("WARNING", f"⚠️ 任务已被取消，跳过数据集 {dataset_name}")
                        return {"status": "cancelled", "message": f"任务被取消，跳过数据集 {dataset_name}"}
                    
                    # 检查全局取消状态（Python API评测）
                    try:
                        from app.api.api_v1.endpoints.evalscope_sync import check_task_cancelled
                        if check_task_cancelled(task_id):
                            reporter.log("WARNING", f"⚠️ 任务 {task_id} 已被取消，停止数据集 {dataset_name} 的评测")
                            return {"status": "cancelled", "message": f"任务被取消，数据集 {dataset_name} 评测已停止"}
                    except Exception as e:
                        reporter.log("WARNING", f"检查取消状态失败: {e}")
                    
                    # 执行评测前保存进程信息（模拟进程启动）
                    import os
                    current_pid = os.getpid()
                    cmd_args = ["python", "-m", "evalscope.cli.cli", "eval", dataset_name]
                    process_manager.save_process_info(dataset_name, current_pid, cmd_args)
                    reporter.log("INFO", f"💾 已保存进程信息: {dataset_name} -> PID {current_pid}")
                    
                    # 执行评测（添加超时和错误处理）
                    try:
                        import signal
                        import threading
                        
                        # 设置超时机制
                        timeout_seconds = 3600  # 1小时超时
                        result = None
                        exception = None
                        
                        def run_eval():
                            nonlocal result, exception
                            try:
                                # 在评测过程中定期检查取消状态
                                import time
                                start_time = time.time()
                                check_interval = 5  # 每5秒检查一次
                                
                                # 由于run_task是阻塞的，我们无法在其中检查取消状态
                                # 但可以在开始前再次确认
                                try:
                                    from app.api.api_v1.endpoints.evalscope_sync import check_task_cancelled
                                    if check_task_cancelled(task_id):
                                        raise Exception(f"任务 {task_id} 已被取消，停止数据集 {dataset_name} 的评测")
                                except Exception as cancel_e:
                                    exception = cancel_e
                                    return
                                
                                result = run_task(eval_config)
                                
                                # 评测完成后再次检查取消状态
                                try:
                                    from app.api.api_v1.endpoints.evalscope_sync import check_task_cancelled
                                    if check_task_cancelled(task_id):
                                        raise Exception(f"任务 {task_id} 在评测过程中被取消")
                                except Exception as cancel_e:
                                    exception = cancel_e
                                    return
                                    
                            except Exception as e:
                                exception = e
                        
                        # 在单独线程中执行评测
                        eval_thread = threading.Thread(target=run_eval)
                        eval_thread.daemon = True
                        eval_thread.start()
                        eval_thread.join(timeout=timeout_seconds)
                        
                        if eval_thread.is_alive():
                            reporter.log("ERROR", f"❌ 评测超时（{timeout_seconds}秒），任务将被标记为失败")
                            raise TimeoutError(f"评测超时，超过{timeout_seconds}秒")
                        
                        if exception:
                            raise exception
                            
                        if result is None:
                            raise RuntimeError("评测执行失败，未返回结果")
                            
                    except Exception as e:
                        reporter.log("ERROR", f"❌ 评测执行失败: {e}")
                        # 尝试从工作目录加载已生成的结果
                        if work_dir.exists():
                            timestamp_dirs = [d for d in work_dir.iterdir() if d.is_dir() and d.name.startswith('2025')]
                            if timestamp_dirs:
                                latest_dir = max(timestamp_dirs, key=lambda x: x.name)
                                reporter.log("INFO", f"🔄 尝试从工作目录加载结果: {latest_dir}")
                                try:
                                    # 使用本地定义的ResultParser类
                                    all_results = ResultParser.load_results_from_json_files(work_dir)
                                    if all_results:
                                        reporter.log("INFO", f"✅ 成功加载 {len(all_results)} 个结果")
                                        return {"status": "loaded", "results": all_results}
                                except Exception as load_error:
                                    reporter.log("WARNING", f"⚠️ 加载结果失败: {load_error}")
                        raise
                    
                    # 评测完成后检查取消状态
                    if getattr(self.request, 'cancelled', False):
                        reporter.log("WARNING", f"⚠️ 任务已被取消，停止处理结果")
                        return {"status": "cancelled", "message": "任务已被取消"}
                    
                    # 解析结果
                    parsed_results = ResultParser.parse_evalscope_result(result, dataset_name)
                    
                    # 更新数据集完成状态
                    reporter.update_dataset_progress(dataset_name, status='completed')
                    reporter.log("INFO", f"✅ 数据集 {dataset_name} 评测完成")
                    
                    # 更新整体进度
                    reporter.update_progress(message=f"完成数据集 {dataset_name}")
                    
                    return dataset_name, parsed_results
                
                # 并行处理多个数据集 - 强制并行
                reporter.log("INFO", f"🚀 使用Python API并行处理 {len(task.datasets)} 个数据集")
                import concurrent.futures
                
                results = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(task.datasets)) as executor:
                    future_to_dataset = {
                        executor.submit(run_single_dataset, dataset): dataset 
                        for dataset in task.datasets
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_dataset):
                        result = future.result()
                        
                        # 处理不同的返回类型
                        if isinstance(result, dict) and result.get('status') == 'cancelled':
                            reporter.log("WARNING", f"⚠️ 数据集评测被取消")
                            continue
                        elif isinstance(result, dict) and result.get('status') == 'loaded':
                            # 从文件加载的结果
                            loaded_results = result.get('results', [])
                            results.extend(loaded_results)
                            continue
                        elif isinstance(result, tuple) and len(result) == 2:
                            # 正常评测结果
                            dataset_name, parsed_results = result
                            results.extend(parsed_results)
                            
                            # 更新数据集完成状态
                            reporter.update_dataset_progress(dataset_name, status='completed')
                            reporter.log("INFO", f"✅ 数据集 {dataset_name} 评测完成")
                            
                            progress = len(results) * 80 / len(task.datasets) + 15
                            reporter.update_progress(int(progress), f"完成数据集 {dataset_name}")
                        else:
                            reporter.log("WARNING", f"⚠️ 未知的返回结果类型: {type(result)}")
                    
                    all_results = results
                
                reporter.log("INFO", "")
                reporter.log("INFO", "🎉 所有数据集评测完成")
                
                # Python API 成功，直接跳转到结果处理
                python_api_success = True
                
            except Exception as api_error:
                reporter.log("WARNING", "")
                reporter.log("WARNING", "⚠️  Python API执行失败，即将回退到命令行方式")
                reporter.log("WARNING", f"💥 错误原因: {api_error}")
                reporter.log("WARNING", f"🔄 回退策略: 使用命令行模式重新执行")
                reporter.log("WARNING", "")
                # 继续使用命令行方式
                python_api_success = False
            
            # 只有Python API失败时才使用命令行方式
            if not python_api_success:
                # 构建evalscope命令 - 支持多数据集并行处理
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
                
                # 强制并行处理所有数据集
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
                
                if actual_eval_type == 'openai_api':
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
                
                # 为所有数据集命令添加工作目录参数和API参数
                for i, (dataset_name, cmd_args) in enumerate(dataset_commands):
                    # 为每个数据集使用独立的工作目录 - 强制拆分目录
                    dataset_work_dir = work_dir / dataset_name
                    dataset_work_dir.mkdir(parents=True, exist_ok=True)
                    reporter.log("INFO", f"🔧 [{dataset_name}] 创建独立工作目录: {dataset_work_dir}")
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
            
                # 执行evalscope命令 - 支持并行处理
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
                
                # 执行evalscope命令 - 支持并行处理
                if len(dataset_commands) > 1:
                    # 多数据集并行处理
                    reporter.log("INFO", f"🚀 开始并行执行 {len(dataset_commands)} 个数据集评测")
                
                def run_dataset_command(dataset_name, cmd_args):
                    """运行单个数据集的命令"""
                    reporter.log("INFO", "")
                    reporter.log("INFO", f"▶️  [{dataset_name}] 开始执行命令行评测")
                    reporter.log("INFO", f"📋 执行命令: {' '.join(cmd_args)}")
                    reporter.log("INFO", "")
                    
                    # 初始化环境变量（避免作用域问题）
                    env = os.environ.copy()
                    
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
                        process_manager.save_process_info(dataset_name, process.pid, cmd_args)
                        reporter.log("INFO", f"💾 保存进程信息: {dataset_name} -> PID {process.pid}")
                    except Exception as e:
                        reporter.log("WARNING", f"保存进程信息失败: {e}")
                    
                    stdout_lines = []
                    stderr_lines = []
                    
                    while True:
                        # 检查任务是否被取消
                        if getattr(self.request, 'cancelled', False):
                            reporter.log("WARNING", f"[{dataset_name}] 任务已被取消，终止评测进程")
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                            raise Exception(f"任务被取消，数据集 {dataset_name} 评测已终止")
                        
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
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(dataset_commands)) as executor:
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
                
                # 解析和保存结果
                all_results = parse_evalscope_output(stdout_lines, task_id)
        
        # 7. 处理结果
        reporter.set_phase('processing_results')
        reporter.update_progress(95, "处理评测结果")
        
        # 如果Python API没有返回可用结果，尝试从JSON文件加载
        if not all_results:
            reporter.log("WARNING", "Python API未返回结果，尝试从JSON文件加载")
            all_results = ResultParser.load_results_from_json_files(work_dir)
        
        # 保存结果到数据库
        if all_results:
            reporter.log("INFO", f"找到 {len(all_results)} 个评测结果")
            for result_data in all_results:
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
            # 创建默认结果
            reporter.log("WARNING", "未能解析结果，创建默认结果")
            for dataset in task.datasets:
                eval_result = EvalScopeResult(
                    task_id=task_id,
                    benchmark=dataset,
                    metric_name='Accuracy',
                    metric_value=None,
                    category='default',
                    subset_name='main',
                    num_samples=None,
                    raw_results={'note': '评测完成但结果解析失败'}
                )
                db.add(eval_result)
        
        # 8. 更新任务状态
        task.status = 'completed'
        task.progress = 100
        task.completed_at = datetime.now()
        
        # 确保数据库更新成功
        try:
            db.commit()
            reporter.log("INFO", "✅ 任务状态已保存到数据库")
        except Exception as commit_error:
            reporter.log("ERROR", f"❌ 保存任务状态失败: {commit_error}")
            db.rollback()
            # 尝试使用原生SQL更新
            try:
                from sqlalchemy import text
                db.execute(text('''
                    UPDATE evalscope_tasks 
                    SET status = 'completed', 
                        progress = 100, 
                        completed_at = :completed_at
                    WHERE id = :task_id
                '''), {
                    'completed_at': datetime.now(),
                    'task_id': task_id
                })
                db.commit()
                reporter.log("INFO", "✅ 使用原生SQL成功更新任务状态")
            except Exception as sql_error:
                reporter.log("ERROR", f"❌ 原生SQL更新也失败: {sql_error}")
                db.rollback()
        
        # 停止进度监控
        reporter.stop_progress_monitoring()
        
        reporter.set_phase('completed')
        reporter.update_progress(100, "任务完成！")
        reporter.log("INFO", "")
        reporter.log("INFO", "=" * 80)
        reporter.log("INFO", f"✅ 任务 {task_id} 执行成功")
        reporter.log("INFO", f"📁 结果目录: {work_dir}")
        reporter.log("INFO", f"📊 结果数量: {len(all_results)}")
        reporter.log("INFO", "=" * 80)
        
        return {
            "status": "success",
            "task_id": task_id,
            "work_dir": str(work_dir),
            "results_count": len(all_results)
        }
    
    except Exception as e:
        # 错误处理
        error_msg = EvalScopeAPIAdapter.format_error_message(e, "任务执行")
        reporter.log("ERROR", f"❌ 任务失败: {error_msg}")
        
        # 停止进度监控
        reporter.stop_progress_monitoring()
        
        if 'task' in locals() and task:
            task.status = 'failed'
            task.error_message = error_msg
            task.completed_at = datetime.now()
            db.commit()
        
        # 重新抛出异常，让Celery记录
        raise
    
    finally:
        db.close()


# WebSocket进度更新函数
async def send_progress_update(task_id: int, progress: int, message: str, detailed_progress: Dict):
    """发送WebSocket进度更新"""
    try:
        from app.core.websocket_manager import websocket_manager
        await websocket_manager.send_progress_update(
            task_id=task_id,
            progress=progress,
            message=message,
            detailed_progress=detailed_progress
        )
    except Exception as e:
        logger.warning(f"WebSocket进度更新失败: {e}")


# 如果Celery不可用，提供错误提示（非模拟，所有代码均使用真实数据）
if not CELERY_AVAILABLE:
    class MockTask:
        """Celery不可用时的占位类，仅用于提供明确的错误提示"""
        def delay(self, *args, **kwargs):
            raise RuntimeError(
                "Celery未安装或不可用。请安装: pip install celery[redis]"
            )
    
    run_real_evaluation_task = MockTask()
    celery_app = None  # 确保celery_app被定义


__all__ = ['run_real_evaluation_task', 'celery_app', 'CELERY_AVAILABLE']