"""
EvalScope评测服务
"""
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from app.models.evalscope_task import EvalScopeTask, EvalScopeResult
from app.schemas import evalscope as schemas
from app.services.benchmark_registry import BenchmarkRegistry
from app.utils.evalscope_adapter import ModelIDResolver, EvalScopeAPIAdapter

logger = logging.getLogger(__name__)


class EvalScopeService:
    """EvalScope评测服务类"""

    @staticmethod
    async def create_task(
        db: Session,
        user_id: int,
        task_data: schemas.TaskCreate
    ) -> EvalScopeTask:
        """创建评测任务"""
        # 处理limit参数
        dataset_args = task_data.dataset_args or {}
        if task_data.limit:
            for dataset in task_data.datasets:
                if dataset not in dataset_args:
                    dataset_args[dataset] = {}
                dataset_args[dataset]['limit'] = task_data.limit

        # 提取用户模型配置
        user_model_config = None
        if hasattr(task_data, 'user_model_config') and task_data.user_model_config:
            user_model_config = task_data.user_model_config
            logger.info(f"从user_model_config获取配置: {user_model_config.get('model_name', 'N/A')}")
        elif hasattr(task_data, 'extra_metadata') and task_data.extra_metadata:
            user_model_config = task_data.extra_metadata.get('user_model_config')
            logger.info(f"从extra_metadata获取配置")
        
        # 🔧 修复：如果model_id是user_config_格式但没有配置，从数据库查询
        if not user_model_config and task_data.model_id.startswith('user_config_'):
            from app.models.user_config import UserModelConfig
            config_id = task_data.model_id.replace('user_config_', '')
            user_config_record = db.query(UserModelConfig).filter(
                UserModelConfig.id == config_id,
                UserModelConfig.is_active == True
            ).first()
            
            if user_config_record:
                user_model_config = {
                    'type': user_config_record.type,
                    'model_name': user_config_record.model_name,
                    'api_key': user_config_record.api_key,
                    'base_url': user_config_record.base_url,
                    'additional_params': user_config_record.additional_params or {}
                }
                logger.info(f"✅ 从数据库查询到用户配置: {user_model_config['model_name']}")
            else:
                logger.error(f"❌ 未找到用户配置: {config_id}")
                raise ValueError(f"用户配置'{task_data.model_id}'不存在或已禁用")
        
        # ✅ 第1步：验证模型是否存在于数据库中
        from app.models.model_config import ModelConfig
        from app.models.model_management import ModelInfo
        from app.models.user_config import UserModelConfig
        
        model_exists = False
        model_id = task_data.model_id
        
        # 检查多个可能的模型来源
        # 1. 检查ModelConfig表（旧的模型配置）
        model_config = db.query(ModelConfig).filter(
            ModelConfig.model_id == model_id,
            ModelConfig.is_active == True
        ).first()
        
        # 2. 检查ModelInfo表（统一模型管理）
        if not model_config:
            model_info = db.query(ModelInfo).filter(
                ModelInfo.model_id == model_id,
                ModelInfo.is_active == True
            ).first()
            if model_info:
                model_exists = True
        else:
            model_exists = True
        
        # 3. 检查UserModelConfig表（用户自定义配置）
        if not model_exists:
            # 检查是否是用户配置ID格式
            if model_id.startswith('user_config_'):
                config_id = model_id.replace('user_config_', '')
                user_config = db.query(UserModelConfig).filter(
                    UserModelConfig.id == config_id,
                    UserModelConfig.is_active == True
                ).first()
                if user_config:
                    model_exists = True
            else:
                # 检查模型名称是否匹配
                user_config = db.query(UserModelConfig).filter(
                    UserModelConfig.model_name == model_id,
                    UserModelConfig.is_active == True
                ).first()
                if user_config:
                    model_exists = True
        
        # 4. 如果有用户模型配置，也认为模型存在
        if not model_exists and user_model_config:
            model_exists = True
        
        # 如果模型不存在，拒绝创建任务
        if not model_exists:
            error_msg = (
                f"模型 '{model_id}' 不存在或未配置。\n"
                f"请先在【大模型管理】中添加并配置该模型后再创建任务。\n"
                f"提示：确保模型已启用且配置正确。"
            )
            logger.error(f"❌ 任务创建失败: {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"✅ 模型验证通过: {model_id}")
        
        # 检查任务名称是否重复，如果重复则自动添加时间戳后缀
        original_task_name = task_data.task_name
        task_name = original_task_name
        name_suffix = 1
        
        # 查询是否存在同名任务
        existing_task = db.query(EvalScopeTask).filter(
            EvalScopeTask.task_name == task_name,
            EvalScopeTask.user_id == user_id
        ).first()
        
        # 如果存在同名任务，自动添加数字后缀
        while existing_task is not None:
            task_name = f"{original_task_name}-{name_suffix}"
            existing_task = db.query(EvalScopeTask).filter(
                EvalScopeTask.task_name == task_name,
                EvalScopeTask.user_id == user_id
            ).first()
            name_suffix += 1
        
        # 如果任务名称被修改了，记录日志
        if task_name != original_task_name:
            logger.info(f"⚠️ 任务名称重复，已自动修改为: {task_name}")
        
        # 使用ModelIDResolver解析模型ID
        resolver = ModelIDResolver(db)
        try:
            resolved_model_name, extra_metadata = resolver.resolve(
                model_id=task_data.model_id,
                user_model_config=user_model_config
            )
            
            logger.info(f"✅ 模型ID解析成功:")
            logger.info(f"   原始ID: {task_data.model_id}")
            logger.info(f"   解析后: {resolved_model_name}")
            
            # 验证解析结果
            if 'resolution_error' in extra_metadata:
                error_msg = f"模型ID解析失败: {extra_metadata['resolution_error']}"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            # 如果是API模型，验证API配置
            if extra_metadata.get('eval_type') == 'openai_api':
                api_config = EvalScopeAPIAdapter.extract_api_config_from_metadata(extra_metadata)
                if not EvalScopeAPIAdapter.validate_api_config(api_config):
                    error_msg = "API配置不完整，缺少必需的api_key或base_url"
                    logger.error(f"❌ {error_msg}")
                    raise ValueError(error_msg)
            
        except Exception as e:
            logger.error(f"❌ 模型ID解析失败: {e}")
            # 解析失败时抛出异常，不再创建任务
            raise ValueError(f"模型配置错误: {str(e)}")
        
        # 自动检测eval_type（如果未指定或与解析结果不一致）
        detected_eval_type = extra_metadata.get('eval_type', task_data.eval_type)
        if task_data.eval_type and task_data.eval_type != detected_eval_type:
            logger.warning(
                f"⚠️ 指定的eval_type({task_data.eval_type})与检测结果({detected_eval_type})不一致，"
                f"将使用检测结果"
            )
        
        # 创建任务记录（使用可能已修改的任务名称）
        task = EvalScopeTask(
            user_id=user_id,
            task_name=task_name,  # 使用去重后的任务名称
            model_id=resolved_model_name,  # 使用解析后的真实模型名
            datasets=task_data.datasets,
            model_args=task_data.model_args,
            dataset_args=dataset_args,
            generation_config=task_data.generation_config,
            eval_backend=task_data.eval_backend,
            eval_type=detected_eval_type,  # 使用检测到的eval_type
            extra_metadata=extra_metadata,  # 保存完整的解析信息
            status='pending',
            progress=0
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # 创建输出目录并设置work_dir
        from pathlib import Path
        work_dir = Path(f'./outputs/evalscope_task_{task.id}')
        work_dir.mkdir(parents=True, exist_ok=True)
        task.work_dir = str(work_dir)
        db.commit()
        
        logger.info(f"✅ 任务创建成功: ID={task.id}, 模型={task.model_id}, 类型={task.eval_type}")
        
        return task

    @staticmethod
    async def get_task(
        db: Session,
        task_id: int,
        user_id: Optional[int] = None
    ) -> Optional[EvalScopeTask]:
        """获取任务详情"""
        query = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id)
        
        if user_id is not None:
            query = query.filter(EvalScopeTask.user_id == user_id)
        
        return query.first()

    @staticmethod
    async def get_tasks(
        db: Session,
        user_id: int,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[EvalScopeTask], int]:
        """获取任务列表"""
        query = db.query(EvalScopeTask).filter(EvalScopeTask.user_id == user_id)
        
        if status:
            query = query.filter(EvalScopeTask.status == status)
        
        total = query.count()
        tasks = query.order_by(EvalScopeTask.created_at.desc()).offset(skip).limit(limit).all()
        
        return tasks, total

    @staticmethod
    async def update_task(
        db: Session,
        task_id: int,
        updates: Dict[str, Any]
    ) -> Optional[EvalScopeTask]:
        """更新任务"""
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        
        if not task:
            return None
        
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        db.commit()
        db.refresh(task)
        
        return task

    @staticmethod
    async def delete_task(
        db: Session,
        task_id: int,
        user_id: Optional[int] = None
    ) -> bool:
        """删除任务（包括对应的output文件）"""
        import shutil
        import os
        from pathlib import Path
        
        query = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id)
        
        # 如果提供了user_id，则添加用户限制
        if user_id is not None:
            query = query.filter(EvalScopeTask.user_id == user_id)
        
        task = query.first()
        
        if not task:
            return False
        
        # 删除数据库记录
        db.delete(task)
        db.commit()
        
        # 删除对应的output目录
        try:
            # 尝试多个可能的output路径
            output_paths = [
                Path(f"./outputs/evalscope_task_{task_id}"),
                Path(f"outputs/evalscope_task_{task_id}"),
                Path(f"../outputs/evalscope_task_{task_id}"),
            ]
            
            # 如果任务有指定work_dir，也尝试删除
            if task.work_dir:
                output_paths.append(Path(task.work_dir))
            
            deleted_paths = []
            for output_dir in output_paths:
                if output_dir.exists() and output_dir.is_dir():
                    shutil.rmtree(output_dir)
                    deleted_paths.append(str(output_dir))
                    print(f"✅ 已删除output目录: {output_dir}")
            
            if deleted_paths:
                print(f"🗑️ 任务{task_id}删除完成，已清理{len(deleted_paths)}个output目录")
            else:
                print(f"ℹ️ 任务{task_id}删除完成，未找到对应的output目录")
                
        except Exception as e:
            print(f"⚠️ 删除任务{task_id}的output目录时出错: {e}")
            # 即使删除output失败，也不影响任务删除的成功状态
        
        return True

    @staticmethod
    async def save_result(
        db: Session,
        task_id: int,
        result_data: Dict[str, Any]
    ) -> EvalScopeResult:
        """保存评测结果"""
        result = EvalScopeResult(
            task_id=task_id,
            benchmark=result_data.get('benchmark'),
            metric_name=result_data.get('metric_name'),
            metric_value=result_data.get('metric_value'),
            category=result_data.get('category'),
            subset_name=result_data.get('subset_name'),
            num_samples=result_data.get('num_samples'),
            raw_results=result_data.get('raw_results', {})
        )
        
        db.add(result)
        db.commit()
        db.refresh(result)
        
        return result

    @staticmethod
    async def get_task_results(
        db: Session,
        task_id: int
    ) -> List[EvalScopeResult]:
        """获取任务的所有结果"""
        return db.query(EvalScopeResult).filter(
            EvalScopeResult.task_id == task_id
        ).all()

    @staticmethod
    async def cancel_task(
        db: Session,
        task_id: int,
        user_id: Optional[int] = None
    ) -> bool:
        """取消任务"""
        import logging
        logger = logging.getLogger(__name__)
        
        task = await EvalScopeService.get_task(db, task_id, user_id)
        
        if not task:
            return False
        
        if task.status not in ['pending', 'running']:
            return False
        
        # 更新任务状态
        task.status = 'cancelled'
        task.completed_at = datetime.now()
        db.commit()
        
        # 发送Celery取消信号
        try:
            from celery import current_app
            
            # 查找Celery任务ID
            celery_task_id = None
            if hasattr(task, 'celery_task_id') and task.celery_task_id:
                celery_task_id = task.celery_task_id
            else:
                # 尝试从extra_metadata中获取
                if task.extra_metadata and 'celery_task_id' in task.extra_metadata:
                    celery_task_id = task.extra_metadata['celery_task_id']
            
            if celery_task_id:
                # 发送取消信号
                current_app.control.revoke(celery_task_id, terminate=True)
                logger.info(f"已发送Celery取消信号: {celery_task_id}")
            else:
                logger.warning(f"任务 {task_id} 未找到Celery任务ID，无法发送取消信号")
                
        except Exception as e:
            logger.error(f"发送Celery取消信号失败: {e}")
            # 即使Celery取消失败，数据库状态已更新，任务仍会被标记为取消
        
        return True


# Benchmark元数据
BENCHMARK_METADATA = {
    'mmlu': {
        'name': 'MMLU',
        'description': '大规模多任务语言理解',
        'category': 'Knowledge',
        'language': 'English',
        'num_samples': 14042,
        'tags': ['knowledge', 'mcq']
    },
    'cmmlu': {
        'name': 'CMMLU',
        'description': '中文多任务语言理解',
        'category': 'Knowledge',
        'language': 'Chinese',
        'num_samples': 11528,
        'tags': ['knowledge', 'mcq', 'chinese']
    },
    'gsm8k': {
        'name': 'GSM8K',
        'description': '小学数学应用题',
        'category': 'Math',
        'language': 'English',
        'num_samples': 1319,
        'tags': ['math', 'reasoning']
    },
    'arc': {
        'name': 'ARC',
        'description': 'AI2推理挑战',
        'category': 'Reasoning',
        'language': 'English',
        'num_samples': 869,
        'tags': ['reasoning', 'mcq']
    },
    'bbh': {
        'name': 'BBH',
        'description': '大模型困难推理',
        'category': 'Reasoning',
        'language': 'English',
        'num_samples': 6511,
        'tags': ['reasoning', 'hard']
    },
    'humaneval': {
        'name': 'HumanEval',
        'description': '代码生成评测',
        'category': 'Coding',
        'language': 'English',
        'num_samples': 164,
        'tags': ['coding', 'python']
    },
    # 更多benchmark...
}


def get_available_benchmarks(
    category: Optional[str] = None,
    language: Optional[str] = None,
    official_only: bool = False
) -> List[Dict[str, Any]]:
    """获取可用的Benchmark列表（含缓存状态）"""
    benchmarks = []
    
    # 根据参数选择基准来源
    if official_only:
        # 使用ModelScope官方基准列表（48个）
        all_benchmarks = BenchmarkRegistry.get_official_benchmarks()
    else:
        # 使用所有基准（包括实验性基准，63个）
        all_benchmarks = BenchmarkRegistry.get_all_benchmarks()
    
    for benchmark_key, info in all_benchmarks.items():
        if category and info['category'] != category:
            continue
        if language and info['language'] != language:
            continue
        
        # 获取真实的缓存状态
        status = get_benchmark_status(benchmark_key)
        
        benchmark_data = {
            **info,
            'name': benchmark_key,  # 使用key作为唯一标识
            'cached': status['cached'] if status else False,
            'cache_status': status['cache_status'] if status else 'not_cached',
            'download_progress': status.get('download_progress') if status else None,
            'last_updated': status.get('last_updated') if status else None,
            'error_message': status.get('error_message') if status else None,
            'cache_path': status.get('cache_path') if status else None
        }
        
        benchmarks.append(benchmark_data)
    
    return benchmarks


async def download_multiple_benchmarks(benchmark_names: List[str], force_redownload: bool = False):
    """下载多个benchmark数据集"""
    import os
    import asyncio
    from app.services.benchmark_registry import BenchmarkRegistry
    
    # 数据集的ModelScope映射
    # 注意：当前ModelScope上的数据集仓库均不可用，需要更新为正确的仓库名称
    DATASET_MAPPING = {
        # 基础LLM基准测试 - 需要验证仓库是否存在
        # 'mmlu': 'modelscope/mmlu',  # 暂时禁用
        # 'cmmlu': 'modelscope/cmmlu',  # 暂时禁用
        # 'ceval': 'modelscope/ceval-exam',  # 暂时禁用
        # 'gsm8k': 'modelscope/gsm8k',  # 暂时禁用
        # 'competition_math': 'AI-ModelScope/competition_math',  # 暂时禁用
        # 'mathbench': 'AI-ModelScope/mathbench',  # 暂时禁用
        
        # ARC数据集暂时不可用 - ModelScope上不存在
        # 'arc': 'AI-ModelScope/ai2_arc',
        # 'arc_challenge': 'AI-ModelScope/ai2_arc',
        
        # 'humaneval': 'modelscope/humaneval',  # 暂时禁用
        # 'hellaswag': 'modelscope/hellaswag',  # 暂时禁用
        # 'winogrande': 'modelscope/winogrande',  # 暂时禁用
        # 'bbh': 'AI-ModelScope/bbh',  # 暂时禁用
        # 'drop': 'AI-ModelScope/drop',  # 暂时禁用
        # 'race': 'AI-ModelScope/race',  # 暂时禁用
        # 'alpaca_eval': 'AI-ModelScope/alpaca_eval',  # 暂时禁用
        
        # 多模态基准测试 - 需要验证仓库是否存在
        # 'mmmu': 'AI-ModelScope/mmmu',  # 暂时禁用
        # 'mmmu_pro': 'AI-ModelScope/mmmu_pro',  # 暂时禁用
        'mm_bench': 'AI-ModelScope/mm_bench',
        'mm_star': 'AI-ModelScope/mm_star',
        
        # 高级基准测试
        'arena_hard': 'AI-ModelScope/arena_hard',
        'truthful_qa': 'AI-ModelScope/truthful_qa',
        'needle_haystack': 'AI-ModelScope/needle_haystack',
        
        # 新增基准测试映射
        'simple_qa': 'AI-ModelScope/simple_qa',
        'docmath': 'AI-ModelScope/docmath',
        'ifeval': 'AI-ModelScope/ifeval',
        'iquiz': 'AI-ModelScope/iquiz',
        'process_bench': 'AI-ModelScope/process_bench',
        'mmlu_redux': 'AI-ModelScope/mmlu_redux',
        'omni_bench': 'AI-ModelScope/omni_bench',
        'real_world_qa': 'AI-ModelScope/real_world_qa',
        'hle': 'AI-ModelScope/hle',
        'general_qa': 'AI-ModelScope/general_qa',
        'data_collection': 'AI-ModelScope/data_collection',
        'aime25': 'AI-ModelScope/aime25',
        'aime24': 'AI-ModelScope/aime24',
        'general_mcq': 'AI-ModelScope/general_mcq',
        'tau_bench': 'AI-ModelScope/tau_bench',
        'tool_bench': 'AI-ModelScope/tool_bench',
        'olympiad_bench': 'AI-ModelScope/olympiad_bench',
        'minerva_math': 'AI-ModelScope/minerva_math',
        'frames': 'AI-ModelScope/frames',
        'trivia_qa': 'AI-ModelScope/trivia_qa',
        'bfcl_v3': 'AI-ModelScope/bfcl_v3',
        'ai2d': 'AI-ModelScope/ai2d',
        'math_500': 'AI-ModelScope/math_500',
        'general_t2i': 'AI-ModelScope/general_t2i',
        'tifa160': 'AI-ModelScope/tifa160',
        'evalmuse': 'AI-ModelScope/evalmuse',
        'genai_bench': 'AI-ModelScope/genai_bench',
        'hpdv2': 'AI-ModelScope/hpdv2',
        'amc': 'AI-ModelScope/amc',
        'gedit': 'AI-ModelScope/gedit',
        'chinese_simpleqa': 'AI-ModelScope/chinese_simpleqa',
        'health_bench': 'AI-ModelScope/health_bench',
        'multi_if': 'AI-ModelScope/multi_if',
        'musr': 'AI-ModelScope/musr',
        'math_vista': 'AI-ModelScope/math_vista',
        'maritime_bench': 'AI-ModelScope/maritime_bench',
        'super_gpqa': 'AI-ModelScope/super_gpqa',
        'live_code_bench': 'AI-ModelScope/live_code_bench',
        'gpqa_diamond': 'AI-ModelScope/gpqa_diamond',
        'general_arena': 'AI-ModelScope/general_arena',
        'cc_bench': 'AI-ModelScope/cc_bench',
    }
    
    started_downloads = []
    already_cached = []
    failed_downloads = []
    
    for name in benchmark_names:
        try:
            # 检查benchmark是否存在
            all_benchmarks = BenchmarkRegistry.get_all_benchmarks()
            if name not in all_benchmarks:
                failed_downloads.append({
                    'name': name,
                    'error': f'Benchmark {name} 不存在'
                })
                continue
            
            # 检查是否已经缓存
            cache_dir = os.path.expanduser(f'~/.cache/modelscope/datasets/{name}')
            if os.path.exists(cache_dir) and not force_redownload:
                already_cached.append(name)
                continue
            
            # 获取对应的ModelScope数据集ID
            dataset_id = DATASET_MAPPING.get(name)
            if not dataset_id:
                failed_downloads.append({
                    'name': name, 
                    'error': f'暂未支持下载 {name} 数据集 - ModelScope仓库不可用'
                })
                continue
                
            # 开始异步下载
            task = asyncio.create_task(_download_dataset_async(name, dataset_id))
            started_downloads.append(name)
            
        except Exception as e:
            failed_downloads.append({
                'name': name,
                'error': f'下载失败: {str(e)}'
            })
    
    return {
        'started_downloads': started_downloads,
        'already_cached': already_cached,
        'failed_downloads': failed_downloads,
        'message': f'开始下载 {len(started_downloads)} 个数据集'
    }


async def _download_dataset_async(benchmark_name: str, dataset_id: str):
    """异步下载数据集"""
    import asyncio
    import logging
    
    logger = logging.getLogger(__name__)
    
    def download_sync():
        try:
            from modelscope import dataset_snapshot_download
            logger.info(f'开始下载数据集: {benchmark_name} ({dataset_id})')
            
            # 更新状态为下载中
            _update_benchmark_cache_status(benchmark_name, 'downloading', 0)
            
            # 下载数据集
            import os
            dataset_path = dataset_snapshot_download(
                dataset_id=dataset_id,
                cache_dir=os.path.expanduser(f'~/.cache/modelscope/datasets/{benchmark_name}')
            )
            
            # 更新状态为已缓存
            _update_benchmark_cache_status(benchmark_name, 'cached', 100)
            logger.info(f'数据集下载完成: {benchmark_name} -> {dataset_path}')
            
        except Exception as e:
            # 更新状态为错误
            _update_benchmark_cache_status(benchmark_name, 'error', 0, str(e))
            logger.error(f'数据集下载失败: {benchmark_name}, 错误: {str(e)}')
    
    # 在线程池中执行同步下载操作
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_sync)


# 全局状态缓存
_benchmark_status_cache = {}


def _update_benchmark_cache_status(benchmark_name: str, status: str, progress: int = 0, error_message: str = None):
    """更新benchmark缓存状态"""
    global _benchmark_status_cache
    
    _benchmark_status_cache[benchmark_name] = {
        'name': benchmark_name,
        'cached': status == 'cached',
        'cache_status': status,
        'download_progress': progress,
        'error_message': error_message,
        'last_updated': datetime.now().isoformat()
    }


def get_benchmark_status(benchmark_name: str):
    """获取单个benchmark的下载状态"""
    import os
    from datetime import datetime
    from app.services.benchmark_registry import BenchmarkRegistry
    
    # 检查benchmark是否存在
    all_benchmarks = BenchmarkRegistry.get_all_benchmarks()
    if benchmark_name not in all_benchmarks:
        return None
    
    # 先检查内存缓存状态
    if benchmark_name in _benchmark_status_cache:
        cached_status = _benchmark_status_cache[benchmark_name]
        # 添加基本信息
        cached_status.update({
            'file_size': all_benchmarks[benchmark_name].get('file_size'),
        })
        # 添加缓存路径
        cache_dir = os.path.expanduser(f'~/.cache/modelscope/datasets/{benchmark_name}')
        cached_status['cache_path'] = cache_dir
        return cached_status
    
    # 检查本地是否已缓存
    cache_dir = os.path.expanduser(f'~/.cache/modelscope/datasets/{benchmark_name}')
    is_cached = os.path.exists(cache_dir) and bool(os.listdir(cache_dir))
    
    # 返回状态信息
    status = {
        'name': benchmark_name,
        'cached': is_cached,
        'cache_status': 'cached' if is_cached else 'not_cached',
        'download_progress': 100 if is_cached else None,
        'file_size': all_benchmarks[benchmark_name].get('file_size'),
        'last_updated': None,
        'error_message': None,
        'cache_path': cache_dir
    }
    
    # 如果已缓存，获取最后修改时间
    if is_cached:
        try:
            mtime = os.path.getmtime(cache_dir)
            status['last_updated'] = datetime.fromtimestamp(mtime).isoformat()
        except:
            pass
    
    return status

