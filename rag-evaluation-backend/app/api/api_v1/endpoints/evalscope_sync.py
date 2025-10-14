"""
EvalScope同步评测API - 简化版，立即可用
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
# import subprocess  # 不再使用命令行执行
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
import threading
import time

from app.api import deps
from app.schemas import evalscope as schemas
from app.services.evalscope_service import EvalScopeService
from app.services.unified_model_service import UnifiedModelService
from app.models.evalscope_task import EvalScopeResult
from app.models.model_config import ModelConfig
from app.models.user import User

router = APIRouter()

# 全局取消状态管理
_cancelled_tasks = set()
_cancel_lock = threading.Lock()

def check_task_cancelled(task_id: int) -> bool:
    """检查任务是否被取消"""
    with _cancel_lock:
        return task_id in _cancelled_tasks

def mark_task_cancelled(task_id: int):
    """标记任务为已取消"""
    with _cancel_lock:
        _cancelled_tasks.add(task_id)

def unmark_task_cancelled(task_id: int):
    """取消任务取消标记"""
    with _cancel_lock:
        _cancelled_tasks.discard(task_id)

@router.get("/models", response_model=List[Dict[str, Any]])
async def get_user_models(
    current_user: User = Depends(deps.get_optional_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    获取用户配置的模型列表
    支持可选认证：
    - 已认证：返回用户个性化的模型列表
    - 未认证：返回公共可用的模型列表
    """
    # 使用统一模型服务
    unified_service = UnifiedModelService(db)
    
    if current_user:
        # 已认证用户：从数据库查询用户的模型配置
        print(f"INFO: 用户 {current_user.name} 请求模型列表")
        models = db.query(ModelConfig).filter(
            ModelConfig.user_id == str(current_user.id),
            ModelConfig.is_active == True
        ).all()
        print(f"INFO: 查询到用户的 {len(models)} 个模型配置")
    else:
        # 未认证用户：查询所有公共可用的模型配置
        print("INFO: 未认证用户请求模型列表，返回公共模型")
        models = db.query(ModelConfig).filter(
            ModelConfig.is_active == True
        ).limit(20).all()
        print(f"INFO: 查询到 {len(models)} 个公共模型配置")
    
    # 转换为前端需要的格式
    model_list = []
    for model in models:
        model_info = {
            "id": model.model_id,
            "name": model.model_name or model.model_id,
            "display_name": model.model_name or model.model_id,
            "type": model.model_type,
            "rating": 2500,  # 默认rating
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "total_battles": 0,
            "win_rate": 0.0,
            "recent_form": [],
            "tier": "Bronze",
            "config": {
                "model_id": model.model_id,
                "model_name": model.model_name,
                "model_type": model.model_type,
                "model_path": model.model_path,
                "api_url": model.api_url,
                "api_key": model.api_key,
                "model_args": model.model_args or {},
                "generation_config": model.generation_config or {}
            }
        }
        model_list.append(model_info)
    
    # 如果没有找到ModelConfig中的模型，尝试从统一模型管理获取
    if not model_list:
        print("INFO: ModelConfig中没有模型，尝试从统一模型管理获取")
        
        if current_user:
            # 已认证用户：获取用户的统一管理模型
            unified_models = await unified_service.get_all_available_models(str(current_user.id))
        else:
            # 未认证用户：获取公共模型
            unified_models = await unified_service.get_public_models()
        
        # 转换统一模型格式为evalscope所需格式
        for model in unified_models:
            model_info = {
                "id": model.get('id'),
                "name": model.get('name'),
                "display_name": model.get('display_name'),
                "type": model.get('model_type'),
                "rating": model.get('quality_rating', 2500) if model.get('quality_rating') else 2500,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "total_battles": 0,
                "win_rate": 0.0,
                "recent_form": [],
                "tier": "Bronze",
                "config": model.get('config', {})
            }
            model_list.append(model_info)
        
        print(f"INFO: 从统一模型管理获取到 {len(model_list)} 个模型")
    
    # 如果还是没有模型，返回空列表
    if not model_list:
        print("WARN: 数据库中没有任何可用的模型配置，返回空列表")
        print("提示：请在【API配置管理】或【大模型管理】中配置模型，然后点击【同步现有模型】按钮")
    
    return model_list

@router.post("/tasks/sync", response_model=schemas.TaskResponse)
async def create_and_run_task_sync(
    task_data: schemas.TaskCreate,
    db: Session = Depends(deps.get_db)
):
    """同步创建并执行评测任务（简化版）
    
    创建任务后立即返回任务对象，然后在后台线程中执行评测
    """
    
    # 验证数据集
    if not task_data.datasets:
        raise HTTPException(status_code=400, detail="至少选择一个数据集")
    
    # 临时使用固定用户ID
    test_user_id = "5bddb026-0a9d-4a87-8958-d97860566dc9"
    
    # 创建任务（带模型验证）
    try:
        task = await EvalScopeService.create_task(
            db=db,
            user_id=test_user_id,
            task_data=task_data
        )
    except ValueError as e:
        # 模型验证失败，返回400错误
        print(f"❌ 任务创建失败: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=str(e)
        )
    except Exception as e:
        # 其他错误
        print(f"❌ 任务创建失败（未知错误）: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"任务创建失败: {str(e)}"
        )
    
    # 立即更新任务状态为running
    task.status = 'running'
    task.started_at = datetime.now(timezone.utc)
    task.progress = 10
    db.commit()
    
    # 清除取消标记
    unmark_task_cancelled(task.id)
    
    # 刷新task对象以确保所有字段都是最新的
    db.refresh(task)
    
    print(f"✅ 任务 {task.id} 创建成功，准备在后台执行评测")
    
    # 启动后台线程执行评测
    import threading
    eval_thread = threading.Thread(
        target=run_eval_in_background,
        args=(task.id, task_data),
        daemon=True
    )
    eval_thread.start()
    
    # 立即返回任务对象（包含ID），前端可以跳转到详情页面
    return task


def run_eval_in_background(task_id: int, task_data: schemas.TaskCreate):
    """在后台线程中执行评测"""
    from app.db.base import SessionLocal
    
    db = SessionLocal()
    try:
        # 获取任务
        from app.models.evalscope_task import EvalScopeTask
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        if not task:
            print(f"❌ 任务 {task_id} 不存在")
            return
        
        print(f"🚀 后台线程开始执行任务 {task_id}")
        
        # 更新进度
        task.progress = 20
        db.commit()
        
        # 创建工作目录
        task_output_dir = Path(task.work_dir)
        task_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 修复模型ID格式问题
        model_id = task.model_id
        print(f"DEBUG: 原始模型ID: {task.model_id}, eval_type: {task.eval_type}")
        
        # 对于API模型，需要特殊处理
        if task.eval_type == 'openai_api':
            # API模型直接使用原始ID
            if model_id and model_id not in ['model', '']:
                print(f"INFO: 使用API模型: {model_id}")
            else:
                raise ValueError(f"API模型ID无效 ({task.model_id})。请在【大模型管理】中正确配置模型。")
        else:
            # 本地模型需要namespace/name格式
            if not model_id or model_id == "model" or model_id.strip() == "":
                # 尝试从extra_metadata中获取用户配置的模型名
                if task.extra_metadata and task.extra_metadata.get('user_model_config'):
                    user_config = task.extra_metadata['user_model_config']
                    if user_config.get('model_name'):
                        model_id = user_config['model_name']
                        print(f"INFO: 从用户配置获取模型名: {model_id}")
                    else:
                        raise ValueError(f"用户配置中没有模型名。请在【大模型管理】中完善模型配置。")
                else:
                    raise ValueError(f"本地模型ID无效 ({task.model_id})。请在【大模型管理】中正确配置模型。")
        
        print(f"使用 Python API 执行评测")
        
        # 使用 EvalScope Python API 而不是命令行
        try:
            # ⚠️ 重要：必须在导入evalscope之前设置，避免多线程时的tqdm锁冲突
            os.environ['TQDM_DISABLE'] = '1'
            
            from evalscope.run import run_task
            from evalscope.config import TaskConfig
            
            # 构建 TaskConfig 参数
            config_params = {
                'model': model_id,
                'datasets': task.datasets,
                'eval_type': task.eval_type,
                'work_dir': str(task_output_dir)
            }
            
            # 添加 limit 参数
            if hasattr(task_data, 'limit') and task_data.limit:
                config_params['limit'] = task_data.limit
            
            # 添加 API 配置
            if task.eval_type == 'openai_api':
                user_config = None
                if task.extra_metadata and task.extra_metadata.get('user_model_config'):
                    user_config = task.extra_metadata['user_model_config']
                elif hasattr(task_data, 'user_model_config') and task_data.user_model_config:
                    user_config = task_data.user_model_config
                
                if user_config:
                    api_url = user_config.get('api_url') or user_config.get('base_url')
                    api_key = user_config.get('api_key')
                    if api_url:
                        config_params['api_url'] = api_url
                    if api_key:
                        config_params['api_key'] = api_key
            
            print(f"TaskConfig 参数: {config_params}")
            
            # 支持多数据集并行处理
            if len(task.datasets) > 1:
                print(f"🚀 检测到 {len(task.datasets)} 个数据集，启用并行处理")
                import concurrent.futures
                
                def run_single_dataset(dataset_name):
                    """运行单个数据集的评测"""
                    print(f"▶️ 开始评测数据集: {dataset_name}")
                    
                    # 检查任务是否被取消
                    if check_task_cancelled(task_id):
                        print(f"⚠️ 任务 {task_id} 已被取消，停止数据集 {dataset_name} 的评测")
                        raise Exception(f"任务被取消，数据集 {dataset_name} 评测已停止")
                    
                    # 为每个数据集创建独立的配置
                    dataset_config = config_params.copy()
                    dataset_config['datasets'] = [dataset_name]
                    
                    # 🔧 为每个数据集创建独立的工作目录，避免文件锁冲突
                    dataset_work_dir = task_output_dir / dataset_name
                    dataset_work_dir.mkdir(parents=True, exist_ok=True)
                    dataset_config['work_dir'] = str(dataset_work_dir)
                    print(f"🔧 [{dataset_name}] 独立工作目录: {dataset_work_dir}")
                    
                    # 创建独立的TaskConfig
                    task_config = TaskConfig(**dataset_config)
                    result = run_task(task_config)
                    
                    # 再次检查任务状态
                    if check_task_cancelled(task_id):
                        print(f"⚠️ 任务 {task_id} 在评测过程中被取消")
                        raise Exception(f"任务被取消，数据集 {dataset_name} 评测已停止")
                    
                    print(f"✅ 数据集 {dataset_name} 评测完成")
                    return dataset_name, result
                
                # 并行执行所有数据集
                from app.core.config import settings
                
                # 限制最大并行数，避免资源过度消耗
                max_workers = min(len(task.datasets), settings.EVALSCOPE_MAX_PARALLEL_DATASETS)
                print(f"📊 最大并行数: {max_workers} (配置上限: {settings.EVALSCOPE_MAX_PARALLEL_DATASETS})")
                
                results = {}
                failed_datasets = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_dataset = {
                        executor.submit(run_single_dataset, dataset): dataset 
                        for dataset in task.datasets
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_dataset):
                        dataset_name = future_to_dataset[future]
                        try:
                            dataset_name, result = future.result()
                            results[dataset_name] = result
                        except Exception as exc:
                            print(f"❌ 数据集 {dataset_name} 评测失败: {exc}")
                            failed_datasets.append(dataset_name)
                            # 不要中断循环，继续处理其他数据集
                            continue
                
                # 记录失败的数据集
                if failed_datasets:
                    print(f"⚠️ 以下数据集执行失败: {', '.join(failed_datasets)}")
                
                print(f"🎉 所有 {len(task.datasets)} 个数据集并行评测完成（成功: {len(results)}, 失败: {len(failed_datasets)}）")
            else:
                # 单个数据集，使用原有逻辑
                # 检查任务是否被取消
                if check_task_cancelled(task_id):
                    print(f"⚠️ 任务 {task_id} 已被取消，停止评测")
                    raise Exception("任务被取消，评测已停止")
                
                task_config = TaskConfig(**config_params)
                results = run_task(task_config)
                
                # 再次检查任务状态
                if check_task_cancelled(task_id):
                    print(f"⚠️ 任务 {task_id} 在评测过程中被取消")
                    raise Exception("任务被取消，评测已停止")
            
            print(f"Python API 执行完成，结果数量: {len(results) if results else 0}")
            
            # 处理结果 - EvalScope返回格式: {dataset_name: Report对象}
            results_parsed = []
            if results:
                print(f"原始结果类型: {type(results)}")
                print(f"原始结果内容: {results}")
                
                if isinstance(results, dict):
                    # EvalScope返回字典格式: {dataset_name: Report对象}
                    for dataset_name, report in results.items():
                        print(f"处理数据集: {dataset_name}, Report类型: {type(report)}")
                        
                        # 检查Report对象是否有metrics属性
                        if hasattr(report, 'metrics') and report.metrics:
                            for metric in report.metrics:
                                metric_name = getattr(metric, 'name', 'accuracy')
                                metric_score = getattr(metric, 'score', 0.0)
                                metric_num = getattr(metric, 'num', 0)
                                
                                # 检查是否有categories和subsets
                                if hasattr(metric, 'categories') and metric.categories:
                                    for category in metric.categories:
                                        category_name = getattr(category, 'name', ['default'])
                                        if isinstance(category_name, list):
                                            category_name = category_name[0] if category_name else 'default'
                                        
                                        if hasattr(category, 'subsets') and category.subsets:
                                            for subset in category.subsets:
                                                subset_name = getattr(subset, 'name', 'main')
                                                subset_score = getattr(subset, 'score', metric_score)
                                                subset_num = getattr(subset, 'num', metric_num)
                                                
                                                results_parsed.append({
                                                    'benchmark': dataset_name,
                                                    'metric_name': metric_name,
                                                    'metric_value': float(subset_score),
                                                    'category': category_name,
                                                    'subset_name': subset_name,
                                                    'num_samples': subset_num
                                                })
                                        else:
                                            # 没有子集，使用类别级别的数据
                                            category_score = getattr(category, 'score', metric_score)
                                            category_num = getattr(category, 'num', metric_num)
                                            
                                            results_parsed.append({
                                                'benchmark': dataset_name,
                                                'metric_name': metric_name,
                                                'metric_value': float(category_score),
                                                'category': category_name,
                                                'subset_name': 'main',
                                                'num_samples': category_num
                                            })
                                else:
                                    # 没有类别，使用指标级别的数据
                                    results_parsed.append({
                                        'benchmark': dataset_name,
                                        'metric_name': metric_name,
                                        'metric_value': float(metric_score),
                                        'category': 'default',
                                        'subset_name': 'main',
                                        'num_samples': metric_num
                                    })
                        else:
                            # 如果没有metrics属性，尝试从Report对象直接提取
                            if hasattr(report, 'score'):
                                results_parsed.append({
                                    'benchmark': dataset_name,
                                    'metric_name': 'overall_score',
                                    'metric_value': float(getattr(report, 'score', 0.0)),
                                    'category': 'default',
                                    'subset_name': 'main',
                                    'num_samples': getattr(report, 'num', 0)
                                })
                else:
                    # 如果不是字典，尝试其他格式
                    print(f"结果不是字典格式，类型: {type(results)}")
                    if hasattr(results, '__iter__'):
                        for result in results:
                            if isinstance(result, dict):
                                results_parsed.append(result)
                            else:
                                print(f"跳过非字典结果: {type(result)}")
            
            print(f"解析到 {len(results_parsed)} 个结果")
            if results_parsed:
                print(f"第一个结果: {results_parsed[0]}")
            
        except Exception as e:
            print(f"Python API 执行异常: {e}")
            import traceback
            traceback.print_exc()
            task.status = 'failed'
            task.error_message = f"评测执行异常: {str(e)}"
            task.completed_at = datetime.now(timezone.utc)
            db.commit()
            return  # 后台线程，无需返回值
        
        # 保存结果到数据库
        for result_data in results_parsed:
            # 确保 result_data 是字典类型
            if not isinstance(result_data, dict):
                print(f"警告: 结果不是字典类型，跳过: {type(result_data)}")
                continue
                
            # 安全地获取结果字段
            benchmark = result_data.get('benchmark', result_data.get('dataset', 'unknown'))
            metric_name = result_data.get('metric_name', result_data.get('metric', 'accuracy'))
            metric_value = result_data.get('metric_value', result_data.get('score', 0.0))
            category = result_data.get('category', 'default')
            subset_name = result_data.get('subset_name', result_data.get('subset', 'main'))
            num_samples = result_data.get('num_samples', result_data.get('total_samples'))
            
            eval_result = EvalScopeResult(
                task_id=task.id,
                benchmark=benchmark,
                metric_name=metric_name,
                metric_value=metric_value,
                category=category,
                subset_name=subset_name,
                num_samples=num_samples,
                raw_results=result_data
            )
            db.add(eval_result)
        
        # 任务完成
        task.status = 'completed'
        task.progress = 100
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
        
        print(f"✅ 任务 {task.id} 执行成功")
        
    except Exception as e:
        print(f"❌ 任务执行出错: {e}")
        import traceback
        traceback.print_exc()
        task.status = 'failed'
        task.error_message = f"任务执行异常: {str(e)}"
        task.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        # 关闭数据库连接
        db.close()
        print(f"🔒 任务 {task_id} 的数据库连接已关闭")


def parse_stdout_for_results(stdout_lines):
    """解析evalscope输出结果"""
    results = []
    
    # 查找结果表格 - 新的格式匹配
    in_table = False
    for line in stdout_lines:
        line = line.strip()
        
        # 检测表格头
        if '| Model' in line and '| Dataset' in line and '| Score' in line:
            in_table = True
            continue
        
        # 检测表格分隔符
        if in_table and line.startswith('+') and '=' in line:
            continue
        
        # 解析数据行
        if in_table and line.startswith('|') and not line.startswith('+='):
            try:
                # 解析格式：| Model | Dataset | Metric | Subset | Num | Score | Cat.0 |
                parts = [p.strip() for p in line.split('|') if p.strip()]
                
                if len(parts) >= 6:  # 至少6列
                    model_name = parts[0] 
                    dataset = parts[1]
                    metric = parts[2]
                    subset = parts[3] if len(parts) > 3 else 'main'
                    num_samples = parts[4] if len(parts) > 4 else '1'
                    score = parts[5] if len(parts) > 5 else '0'
                    
                    # 转换数据类型
                    try:
                        score_float = float(score)
                    except:
                        score_float = None
                    
                    try:
                        num_int = int(num_samples)
                    except:
                        num_int = None
                    
                    results.append({
                        'benchmark': dataset,
                        'metric_name': metric,
                        'metric_value': score_float,
                        'category': 'default',
                        'subset_name': subset,
                        'num_samples': num_int,
                        'raw_results': {
                            'model': model_name,
                            'parsed_from': 'stdout_table'
                        }
                    })
                    
                    print(f"解析到结果: {dataset} - {metric} = {score}")
            except Exception as e:
                print(f"解析表格行失败: {line} -> {e}")
    
    print(f"总共解析到 {len(results)} 个结果")
    return results
