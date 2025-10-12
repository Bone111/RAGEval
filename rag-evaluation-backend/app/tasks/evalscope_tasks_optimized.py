"""
EvalScope真实评测异步任务 - 优化版本
- 移除命令行回退方式，统一使用Python API
- 优化模型ID处理，使用适配器
- 增强错误处理和日志
- 改进进度跟踪和结果解析
"""
import os
import json
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

# Celery配置
try:
    from celery import Celery
    
    # ==================== 环境变量验证 ====================
    # 目的：确保Celery配置完整，避免使用默认值导致的隐藏问题
    # 问题定位：如果这里抛出ValueError，说明环境变量未正确配置
    # 解决方案：在启动脚本或.env文件中设置 CELERY_BROKER_URL 和 CELERY_RESULT_BACKEND
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

from app.utils.evalscope_adapter import EvalScopeAPIAdapter

logger = logging.getLogger(__name__)


def get_db_session():
    """获取数据库会话"""
    from app.models import user, evalscope_task
    from app.db.base import SessionLocal
    return SessionLocal()


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
    
    def update_progress(self, progress: int = None, message: str = ""):
        """更新进度到数据库和WebSocket"""
        from app.models.evalscope_task import EvalScopeTask
        
        task = self.db.query(EvalScopeTask).filter(
            EvalScopeTask.id == self.task_id
        ).first()
        
        if task:
            # 使用计算的整体进度
            overall_progress = self._calculate_overall_progress() if progress is None else progress
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
            # EvalScope result结构可能不同，需要适配
            # 这里假设result是一个包含评测指标的字典
            if isinstance(result, dict):
                # 尝试提取常见的结果结构
                for metric_name, metric_value in result.items():
                    if isinstance(metric_value, (int, float)):
                        parsed_results.append({
                            'benchmark': dataset_name,
                            'metric_name': metric_name,
                            'metric_value': float(metric_value),
                            'category': 'default',
                            'subset_name': 'main',
                            'num_samples': None
                        })
            
            # 如果无法解析，返回空列表
            if not parsed_results:
                logger.warning(f"无法解析数据集 {dataset_name} 的结果: {result}")
                
        except Exception as e:
            logger.error(f"解析结果时出错: {e}")
        
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
                                        # 计算加权平均
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
                                                'category': 'default',
                                                'subset_name': 'aggregated',
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


@celery_app.task(bind=True, name='evalscope.run_real_evaluation')
def run_real_evaluation_task(self, task_id: int):
    """执行真实的EvalScope评测任务 - 优化版本"""
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
        
        # 3. 准备工作目录
        work_dir = Path(f'./outputs/evalscope_task_{task_id}')
        work_dir.mkdir(parents=True, exist_ok=True)
        task.work_dir = str(work_dir)
        db.commit()
        
        # 启动进度监控
        reporter.start_progress_monitoring(work_dir)
        
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
        
        # 6. 使用Python API执行评测
        reporter.log("INFO", "")
        reporter.log("INFO", "=" * 80)
        reporter.log("INFO", "🚀 使用 EvalScope Python API 进行评测")
        reporter.log("INFO", "=" * 80)
        
        try:
            from evalscope.run import run_task
            from evalscope.config import TaskConfig
            
            reporter.set_phase('evaluating')
            reporter.update_progress(15, "开始评测")
            
            # 为每个数据集单独评测
            all_results = []
            
            for idx, dataset_name in enumerate(task.datasets):
                reporter.log("INFO", f"")
                reporter.log("INFO", f"▶️  [{idx+1}/{len(task.datasets)}] 评测数据集: {dataset_name}")
                reporter.update_dataset_progress(dataset_name, status='running', current_step='准备')
                
                # 构建TaskConfig参数
                config_params = EvalScopeAPIAdapter.build_task_config_params(
                    model_name=model_name,
                    datasets=[dataset_name],
                    eval_type=eval_type,
                    work_dir=str(work_dir / dataset_name if len(task.datasets) > 1 else work_dir),
                    api_config=api_config,
                    model_args=task.model_args,
                    generation_config=task.generation_config,
                    dataset_args=task.dataset_args,
                    limit=task.dataset_args.get(dataset_name, {}).get('limit') if task.dataset_args else None
                )
                
                # 输出配置（隐藏敏感信息）
                config_debug = {k: ('***' if k == 'api_key' else v) for k, v in config_params.items()}
                reporter.log("INFO", f"📋 配置参数:")
                for key, value in config_debug.items():
                    reporter.log("INFO", f"   • {key}: {value}")
                
                # 创建TaskConfig并执行
                eval_config = TaskConfig(**config_params)
                reporter.log("INFO", f"🚀 开始评测...")
                
                # 执行评测
                result = run_task(eval_config)
                
                # 解析结果
                parsed_results = ResultParser.parse_evalscope_result(result, dataset_name)
                all_results.extend(parsed_results)
                
                # 更新数据集完成状态
                reporter.update_dataset_progress(dataset_name, status='completed')
                reporter.log("INFO", f"✅ 数据集 {dataset_name} 评测完成")
                
                # 更新整体进度
                reporter.update_progress(message=f"完成数据集 {dataset_name}")
            
            reporter.log("INFO", "")
            reporter.log("INFO", "🎉 所有数据集评测完成")
            
        except Exception as e:
            error_msg = EvalScopeAPIAdapter.format_error_message(e, "EvalScope评测")
            reporter.log("ERROR", f"❌ 评测失败: {error_msg}")
            raise Exception(f"EvalScope评测失败: {error_msg}")
        
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
        db.commit()
        
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

