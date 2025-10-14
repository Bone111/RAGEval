"""
EvalScope评测API端点
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio
import json
import os
from pathlib import Path

from app.api import deps
from app.schemas import evalscope as schemas
from app.services.evalscope_service import (
    EvalScopeService, 
    get_available_benchmarks,
    download_multiple_benchmarks,
    get_benchmark_status
)
from app.services.unified_model_service import UnifiedModelService
from app.models.user import User
from app.models.evalscope_task import EvalScopeResult, EvalScopeTask
from app.tasks.task_monitor import check_stuck_tasks
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# 翻译请求模型
class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "zh"

class TranslateResponse(BaseModel):
    translated_text: str

# WebSocket连接管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, List[WebSocket]] = {}

    async def connect(self, task_id: int, websocket: WebSocket):
        await websocket.accept()
        if task_id not in self.active_connections:
            self.active_connections[task_id] = []
        self.active_connections[task_id].append(websocket)

    def disconnect(self, task_id: int, websocket: WebSocket):
        if task_id in self.active_connections:
            self.active_connections[task_id].remove(websocket)

    async def send_message(self, task_id: int, message: dict):
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass

ws_manager = ConnectionManager()


# ==================== 真实评测逻辑 ====================
# 模拟评测函数已移除，现在使用真实的EvalScope命令行工具


# ==================== 任务管理 ====================

@router.post("/tasks", response_model=schemas.TaskResponse)
async def create_task(
    task_data: schemas.TaskCreate,
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """创建评测任务（临时移除认证）"""
    # 验证数据集
    if not task_data.datasets:
        raise HTTPException(status_code=400, detail="至少选择一个数据集")
    
    # 临时使用固定用户ID进行测试
    test_user_id = "5bddb026-0a9d-4a87-8958-d97860566dc9"  # 使用现有管理员ID
    
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
    
    # 提交真实的评测任务
    try:
        # 使用统一版本的任务
        try:
            from app.tasks.evalscope_tasks import run_real_evaluation_task, CELERY_AVAILABLE
            evaluation_task = run_real_evaluation_task
            use_fixed = False
            print(f"✅ 使用统一版本任务，CELERY_AVAILABLE: {CELERY_AVAILABLE}")
        except ImportError as e:
            print(f"❌ 统一版本导入失败: {e}")
            raise HTTPException(
                status_code=500,
                detail="评测任务模块无法导入，请检查Celery配置"
            )
        
        print(f"evaluation_task: {evaluation_task}")
        print(f"evaluation_task type: {type(evaluation_task)}")
        print(f"CELERY_AVAILABLE: {CELERY_AVAILABLE}")
        
        if CELERY_AVAILABLE and evaluation_task:
            # 使用真实的evalscope评测
            print(f"🚀 提交任务到Celery: {task.id}")
            print(f"evaluation_task before delay: {evaluation_task}")
            print(f"evaluation_task type before delay: {type(evaluation_task)}")
            print(f"evaluation_task is None: {evaluation_task is None}")
            print(f"hasattr delay: {hasattr(evaluation_task, 'delay')}")
            try:
                result = evaluation_task.delay(task.id)
                print(f"delay调用成功，结果: {result}")
            except Exception as delay_error:
                print(f"delay调用失败: {delay_error}")
                raise delay_error
            task.status = 'pending'
            task.error_message = None
            
            # 记录使用的版本
            if not task.extra_metadata:
                task.extra_metadata = {}
            task.extra_metadata['task_version'] = 'fixed' if use_fixed else ('optimized' if not use_fixed else 'legacy')
            
            db.commit()
            print(f"✅ 任务提交成功")
        else:
            # Celery不可用时的处理
            print(f"❌ Celery不可用或任务函数为空")
            task.status = 'failed'
            task.error_message = f"Celery不可用或任务函数为空: CELERY_AVAILABLE={CELERY_AVAILABLE}, evaluation_task={evaluation_task}"
            db.commit()
            
    except Exception as e:
        # 如果任务提交失败
        print(f"❌ 任务提交异常: {e}")
        task.status = 'failed'
        task.error_message = f"任务提交失败: {str(e)}"
        db.commit()
    
    return task


@router.get("/tasks", response_model=schemas.TaskList)
async def get_tasks(
    status: Optional[str] = Query(None, description="任务状态筛选"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """获取任务列表（临时移除认证）"""
    # 临时获取所有任务
    from app.models.evalscope_task import EvalScopeTask
    from sqlalchemy import desc
    
    query = db.query(EvalScopeTask)
    if status:
        query = query.filter(EvalScopeTask.status == status)
    
    total_count = query.count()
    tasks = query.order_by(desc(EvalScopeTask.created_at)).offset(skip).limit(limit).all()
    
    return schemas.TaskList(total=total_count, tasks=tasks)


@router.get("/tasks/{task_id}", response_model=schemas.TaskDetail)
async def get_task(
    task_id: int,
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """获取任务详情（临时移除认证）"""
    from sqlalchemy.orm import joinedload
    
    # 使用joinedload预加载results关系
    task = db.query(EvalScopeTask).options(
        joinedload(EvalScopeTask.results)
    ).filter(EvalScopeTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 计算有效执行时长
    task.effective_duration = task.get_effective_duration()
    
    return task


@router.get("/tasks/{task_id}/dataset-progress")
async def get_task_dataset_progress(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """获取任务的数据集进度详情"""
    task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    import os
    from pathlib import Path
    
    dataset_progress = {}
    
    # 数据集配置映射（从配置文件获取subset_list）
    dataset_configs = {}
    
    # 动态从任务配置文件中读取subset_list
    for dataset_name in task.datasets:
        # 查找配置文件
        config_files = []
        if task.work_dir:
            # 尝试多个可能的路径
            possible_paths = [
                Path(task.work_dir) / dataset_name / "configs",
                Path(f"outputs/evalscope_task_{task_id}") / dataset_name / "configs",
            ]
            
            for path_pattern in possible_paths:
                if path_pattern.exists():
                    config_files = list(path_pattern.glob("*.yaml"))
                    break
            
            # 如果直接路径不存在，尝试查找带时间戳的路径
            if not config_files:
                import glob
                patterns = [
                    f"outputs/evalscope_task_{task_id}/{dataset_name}/*/configs/*.yaml",
                    f"outputs/evalscope_task_{task_id}/*/configs/*.yaml"
                ]
                for pattern in patterns:
                    config_files = [Path(f) for f in glob.glob(pattern)]
                    if config_files:
                        break
        
        # 读取配置文件获取subset_list
        subsets = []
        limit = 5  # 默认限制
        
        if config_files:
            try:
                import yaml
                with open(config_files[0], 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                    
                # 从dataset_args中获取subset_list
                if 'dataset_args' in config_data and dataset_name in config_data['dataset_args']:
                    dataset_config = config_data['dataset_args'][dataset_name]
                    subsets = dataset_config.get('subset_list', [])
                    limit = dataset_config.get('limit', 5)
                    
            except Exception as e:
                print(f"读取配置文件失败: {e}")
        
        # 如果无法从配置文件读取，跳过该数据集
        if not subsets:
            print(f"警告: 无法从配置文件读取数据集 {dataset_name} 的subset_list，跳过该数据集")
            continue
        
        dataset_configs[dataset_name] = {
            'subsets': subsets,
            'limit': limit
        }
    
    # 如果task有dataset_args，优先使用
    if task.dataset_args:
        for dataset_name, config in task.dataset_args.items():
            if dataset_name in dataset_configs:
                dataset_configs[dataset_name]['limit'] = config.get('limit', 5)
    
    for dataset_name in task.datasets:
        if dataset_name not in dataset_configs:
            continue
            
        config = dataset_configs[dataset_name]
        subsets = config['subsets']
        limit = config['limit']
        
        # 查找predictions目录
        predictions_dir = None
        if task.work_dir:
            # 尝试多个可能的路径
            possible_paths = [
                Path(task.work_dir) / dataset_name / "predictions",
                Path(f"outputs/evalscope_task_{task_id}") / dataset_name / "predictions",
            ]
            
            for path_pattern in possible_paths:
                if path_pattern.exists():
                    predictions_dir = path_pattern
                    break
            
            # 如果直接路径不存在，尝试查找带时间戳的路径
            if not predictions_dir:
                import glob
                patterns = [
                    f"outputs/evalscope_task_{task_id}/{dataset_name}/*/predictions",
                    f"outputs/evalscope_task_{task_id}/*/predictions"
                ]
                for pattern in patterns:
                    matches = glob.glob(pattern)
                    if matches:
                        predictions_dir = Path(matches[0])
                        # 查找模型子目录
                        model_dirs = list(predictions_dir.glob("*"))
                        if model_dirs:
                            predictions_dir = model_dirs[0]  # 使用第一个模型目录
                        break
        
        subset_progress = {}
        total_completed = 0
        total_expected = len(subsets) * limit
        
        if predictions_dir and predictions_dir.exists():
            # 检查每个子集的预测文件
            for subset in subsets:
                subset_file = predictions_dir / f"{dataset_name}_{subset}.jsonl"
                if subset_file.exists():
                    try:
                        with open(subset_file, 'r', encoding='utf-8') as f:
                            completed_samples = len(f.readlines())
                    except:
                        completed_samples = 0
                else:
                    completed_samples = 0
                
                subset_progress[subset] = {
                    'completed_samples': completed_samples,
                    'total_samples': limit,
                    'progress': min(int(completed_samples / limit * 100), 100) if limit > 0 else 0
                }
                total_completed += completed_samples
        else:
            # 如果没有predictions目录，所有子集进度为0
            for subset in subsets:
                subset_progress[subset] = {
                    'completed_samples': 0,
                    'total_samples': limit,
                    'progress': 0
                }
        
        # 确定数据集状态
        # 优先检查该数据集是否已完成（100%）
        if total_expected > 0 and total_completed >= total_expected:
            dataset_status = 'completed'  # ✅ 该数据集已100%完成
        elif task.status == 'completed':
            dataset_status = 'completed'
        elif task.status == 'running':
            dataset_status = 'running' if total_completed > 0 else 'pending'
        elif task.status == 'paused':
            dataset_status = 'paused'
        elif task.status == 'failed':
            dataset_status = 'failed'
        else:
            dataset_status = 'pending'
        
        dataset_progress[dataset_name] = {
            'subsets': subset_progress,
            'total_completed': total_completed,
            'total_expected': total_expected,
            'overall_progress': min(int(total_completed / total_expected * 100), 100) if total_expected > 0 else 0,
            'status': dataset_status
        }
    
    return {
        'task_id': task_id,
        'dataset_progress': dataset_progress
    }


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """删除任务（临时移除认证）"""
    success = await EvalScopeService.delete_task(
        db=db,
        task_id=task_id,
        user_id=None  # 临时不限制用户
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在或无权删除")
    
    return {"success": True, "message": "任务已删除"}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: int,
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """取消任务（临时移除认证）"""
    success = await EvalScopeService.cancel_task(
        db=db,
        task_id=task_id,
        user_id=None  # 临时不限制用户
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="任务不存在、无权取消或任务已完成"
        )
    
    return {"success": True, "message": "任务已取消"}


@router.post("/tasks/{task_id}/pause")
async def pause_task(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """暂停任务 - 使用进程管理器终止所有相关进程"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.core.process_manager import ProcessManager
        
        # 查找任务
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task.status not in ['running', 'paused']:
            raise HTTPException(status_code=400, detail="只能暂停运行中或已暂停的任务")
        
        # 使用进程管理器暂停任务
        process_manager = ProcessManager(task_id)
        success, terminated_processes = process_manager.pause_task()
        
        if success:
            # 更新任务状态
            task.status = 'paused'
            if not task.extra_metadata:
                task.extra_metadata = {}
            task.extra_metadata['paused_at'] = datetime.now().isoformat()
            
            # 标记任务为已取消（用于Python API评测）
            try:
                from app.api.api_v1.endpoints.evalscope_sync import mark_task_cancelled
                mark_task_cancelled(task_id)
                logger.info(f"任务 {task_id} 已标记为暂停状态")
            except Exception as e:
                logger.warning(f"标记任务暂停状态失败: {e}")
            task.extra_metadata['terminated_processes'] = terminated_processes
            db.commit()
            
            if terminated_processes:
                message = f"任务已暂停，终止了 {len(terminated_processes)} 个进程: {', '.join(terminated_processes)}"
            else:
                message = "任务已暂停，未发现运行中的进程"
            
            logger.info(f"任务 {task_id} 暂停成功: {message}")
            return {"success": True, "message": message, "terminated_processes": terminated_processes}
        else:
            raise HTTPException(status_code=500, detail="暂停任务失败")
            
    except Exception as e:
        logger.error(f"暂停任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"暂停任务失败: {str(e)}")


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """恢复任务 - 使用进程管理器检查现有结果并继续执行"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.core.process_manager import ProcessManager
        
        # 查找任务
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task.status not in ['paused']:
            raise HTTPException(status_code=400, detail="只能恢复已暂停的任务")
        
        # 使用进程管理器检查可继续的数据集
        process_manager = ProcessManager(task_id)
        success, resumable_datasets = process_manager.resume_task()
        
        if not success:
            raise HTTPException(status_code=500, detail="检查可继续数据集失败")
        
        # 更新任务状态
        task.status = 'running'
        
        # 清除取消标记（用于Python API评测）
        try:
            from app.api.api_v1.endpoints.evalscope_sync import unmark_task_cancelled
            unmark_task_cancelled(task_id)
            logger.info(f"任务 {task_id} 已清除取消标记")
        except Exception as e:
            logger.warning(f"清除任务取消标记失败: {e}")
        # 记录恢复时间，用于计算暂停时长
        resumed_at = datetime.now()
        task.started_at = resumed_at
        
        # 计算暂停时长并累加
        if task.extra_metadata and 'paused_at' in task.extra_metadata:
            paused_at = datetime.fromisoformat(task.extra_metadata['paused_at'])
            pause_duration = int((resumed_at - paused_at).total_seconds())
            task.add_pause_duration(pause_duration)
        
        if not task.extra_metadata:
            task.extra_metadata = {}
        task.extra_metadata['resumed_at'] = resumed_at.isoformat()
        task.extra_metadata['resumable_datasets'] = resumable_datasets
        db.commit()
        
        # 重新启动任务（使用use_cache功能）
        logger.info(f"恢复任务 {task_id}，可继续的数据集: {resumable_datasets}")
        from app.tasks.evalscope_tasks import run_real_evaluation_task
        result = run_real_evaluation_task.delay(task_id)
        
        # 更新Celery任务ID
        task.celery_task_id = result.id
        if not task.extra_metadata:
            task.extra_metadata = {}
        task.extra_metadata['celery_task_id'] = result.id
        db.commit()
        
        message = f"任务已恢复，将从断点继续执行"
        if resumable_datasets:
            message += f"，可继续的数据集: {', '.join(resumable_datasets)}"
        
        return {"success": True, "message": message, "resumable_datasets": resumable_datasets}
            
    except Exception as e:
        logger.error(f"恢复任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"恢复任务失败: {str(e)}")


@router.get("/tasks/{task_id}/process-status")
async def get_task_process_status(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """获取任务的进程状态"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.core.process_manager import ProcessManager
        
        # 查找任务
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取进程状态
        process_manager = ProcessManager(task_id)
        process_status = process_manager.get_task_status()
        
        return {
            "success": True,
            "task_id": task_id,
            "task_status": task.status,
            "process_status": process_status
        }
            
    except Exception as e:
        logger.error(f"获取进程状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取进程状态失败: {str(e)}")


@router.get("/tasks/{task_id}/check-results")
async def check_task_results(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """检查任务是否有评测结果目录"""
    import logging
    from pathlib import Path
    import glob
    logger = logging.getLogger(__name__)
    
    try:
        # 查找任务
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 检查是否有输出目录
        task_output_dir = Path(f'./outputs/evalscope_task_{task_id}')
        has_results = False
        
        if task_output_dir.exists():
            # 检查是否有predictions目录（支持多层目录结构）
            predictions_pattern = str(task_output_dir / "*" / "*" / "predictions")
            predictions_dirs = glob.glob(predictions_pattern)
            
            if predictions_dirs:
                # 检查是否有实际的预测文件（包括子目录中的文件）
                for pred_dir in predictions_dirs:
                    pred_path = Path(pred_dir)
                    if pred_path.exists():
                        # 检查当前目录和所有子目录中的jsonl文件
                        jsonl_files = list(pred_path.rglob("*.jsonl"))
                        if jsonl_files:
                            has_results = True
                            break
        
        return {
            "task_id": task_id,
            "has_results": has_results,
            "output_dir": str(task_output_dir),
            "exists": task_output_dir.exists()
        }
            
    except Exception as e:
        logger.error(f"检查任务结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查任务结果失败: {str(e)}")


@router.post("/tasks/{task_id}/continue")
async def continue_task(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """继续评测任务 - 在已有结果基础上继续"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # 查找任务
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task.status in ['running']:
            raise HTTPException(status_code=400, detail="任务正在运行中，无法继续评测")
        
        # 检查是否有工作目录可以继续
        if not task.work_dir:
            # 如果没有工作目录，尝试使用默认路径
            from pathlib import Path
            default_work_dir = Path(f'./outputs/evalscope_task_{task_id}')
            if default_work_dir.exists():
                task.work_dir = str(default_work_dir)
            else:
                raise HTTPException(status_code=400, detail="任务没有工作目录，无法继续评测")
        
        # 更新任务状态
        task.status = 'running'
        task.error_message = None  # 清空错误信息
        # 记录继续时间，用于计算暂停时长
        continued_at = datetime.now()
        task.started_at = continued_at
        
        # 计算暂停时长并累加（如果有暂停记录）
        if task.extra_metadata and 'paused_at' in task.extra_metadata:
            paused_at = datetime.fromisoformat(task.extra_metadata['paused_at'])
            pause_duration = int((continued_at - paused_at).total_seconds())
            task.add_pause_duration(pause_duration)
        
        if not task.extra_metadata:
            task.extra_metadata = {}
        task.extra_metadata['continued_at'] = continued_at.isoformat()
        db.commit()
        
        # 重新启动任务（使用use_cache功能实现断点续评）
        logger.info(f"继续评测任务 {task_id}，使用EvalScope断点续评功能")
        from app.tasks.evalscope_tasks import run_real_evaluation_task
        result = run_real_evaluation_task.delay(task_id)
        
        # 更新Celery任务ID
        task.celery_task_id = result.id
        task.extra_metadata['celery_task_id'] = result.id
        db.commit()
        
        return {"success": True, "message": "任务已继续评测，将从断点继续执行"}
            
    except Exception as e:
        logger.error(f"继续评测任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"继续评测任务失败: {str(e)}")


@router.post("/tasks/{task_id}/restart")
async def restart_task(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """重新评测任务 - 覆盖原文件夹重新开始"""
    import logging
    import shutil
    from pathlib import Path
    logger = logging.getLogger(__name__)
    
    try:
        from celery import current_app
        
        # 查找任务
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 清理原输出目录 - 强制清理任务目录（在状态检查之前）
        task_output_dir = Path(f'./outputs/evalscope_task_{task_id}')
        if task_output_dir.exists():
            logger.info(f"清理任务 {task_id} 的输出目录: {task_output_dir}")
            shutil.rmtree(task_output_dir)
        
        if task.status in ['running']:
            raise HTTPException(status_code=400, detail="任务正在运行中，无法重新评测")
        
        # 重置任务状态
        task.status = 'pending'
        task.celery_task_id = None
        task.work_dir = None
        task.error_message = None  # 清空错误信息
        task.started_at = None      # 重置开始时间
        task.completed_at = None    # 重置完成时间
        task.progress = 0           # 重置进度
        if not task.extra_metadata:
            task.extra_metadata = {}
        task.extra_metadata.pop('celery_task_id', None)
        task.extra_metadata['restarted_at'] = datetime.now().isoformat()
        
        # 确保数据库更新生效
        db.commit()
        db.refresh(task)  # 刷新对象状态
        
        # 重新启动任务
        logger.info(f"重新启动任务 {task_id}")
        from app.tasks.evalscope_tasks import run_real_evaluation_task
        result = run_real_evaluation_task.delay(task_id)
        
        # 更新Celery任务ID
        task.celery_task_id = result.id
        task.extra_metadata['celery_task_id'] = result.id
        db.commit()
        
        return {"success": True, "message": "任务已重新启动"}
            
    except Exception as e:
        logger.error(f"重新评测任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"重新评测任务失败: {str(e)}")


@router.get("/worker/status")
async def get_worker_status():
    """获取Worker状态"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from celery import current_app
        
        # 获取活跃的worker信息
        inspect = current_app.control.inspect()
        active_workers = inspect.active()
        stats = inspect.stats()
        
        worker_info = []
        if active_workers:
            for worker_name, tasks in active_workers.items():
                worker_data = {
                    "name": worker_name,
                    "active_tasks": len(tasks),
                    "tasks": tasks,
                    "stats": stats.get(worker_name, {}) if stats else {}
                }
                worker_info.append(worker_data)
        
        return {
            "success": True,
            "workers": worker_info,
            "total_workers": len(worker_info),
            "total_active_tasks": sum(len(tasks) for tasks in active_workers.values()) if active_workers else 0
        }
        
    except Exception as e:
        logger.error(f"获取Worker状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取Worker状态失败: {str(e)}")


@router.post("/worker/pause-all")
async def pause_all_workers():
    """暂停所有Worker"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from celery import current_app
        
        # 暂停所有worker
        current_app.control.broadcast('pool_pause')
        logger.info("已暂停所有Worker")
        
        return {"success": True, "message": "所有Worker已暂停"}
        
    except Exception as e:
        logger.error(f"暂停所有Worker失败: {e}")
        raise HTTPException(status_code=500, detail=f"暂停所有Worker失败: {str(e)}")


@router.post("/worker/resume-all")
async def resume_all_workers():
    """恢复所有Worker"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from celery import current_app
        
        # 恢复所有worker
        current_app.control.broadcast('pool_resume')
        logger.info("已恢复所有Worker")
        
        return {"success": True, "message": "所有Worker已恢复"}
        
    except Exception as e:
        logger.error(f"恢复所有Worker失败: {e}")
        raise HTTPException(status_code=500, detail=f"恢复所有Worker失败: {str(e)}")


# ==================== 结果查询 ====================

@router.get("/tasks/{task_id}/results", response_model=List[schemas.EvalResultResponse])
async def get_task_results(
    task_id: int,
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """获取任务的所有结果（临时移除认证）"""
    results = await EvalScopeService.get_task_results(db, task_id)
    return results


# ==================== Benchmark信息 ====================

@router.get("/benchmarks", response_model=schemas.BenchmarkListResponse)
async def get_benchmarks(
    category: Optional[str] = Query(default=None, description="分类筛选"),
    language: Optional[str] = Query(default=None, description="语言筛选"),
    official_only: bool = Query(default=False, description="仅显示ModelScope官方基准（48个）")
):
    """获取可用的Benchmark列表（含缓存状态）"""
    benchmarks = get_available_benchmarks(
        category=category, 
        language=language, 
        official_only=official_only
    )
    
    benchmark_list = [
        schemas.BenchmarkInfo(
            name=b['name'],
            display_name=b['display_name'],
            description=b['description'],
            category=b['category'],
            language=b['language'],
            num_samples=b.get('num_samples'),
            tags=b.get('tags', []),
            cached=b.get('cached', False),
            cache_status=b.get('cache_status', 'not_cached'),
            download_progress=b.get('download_progress'),
            file_size=b.get('file_size'),
            last_updated=b.get('last_updated'),
            cache_path=b.get('cache_path'),
            num_subsets=b.get('num_subsets')
        )
        for b in benchmarks
    ]
    
    return schemas.BenchmarkListResponse(
        total=len(benchmark_list),
        benchmarks=benchmark_list
    )


@router.post("/benchmarks/download")
async def download_benchmarks(
    download_request: schemas.BenchmarkDownloadRequest,
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """批量下载benchmarks（临时移除认证）"""
    result = await download_multiple_benchmarks(
        benchmark_names=download_request.benchmark_names,
        force_redownload=download_request.force_redownload
    )
    
    return result


@router.post("/benchmarks/download-all")
async def download_all_benchmarks(
    force_redownload: bool = False,
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """一键下载所有benchmarks（临时移除认证）"""
    # 获取所有可用的基准测试
    all_benchmarks = get_available_benchmarks()
    benchmark_names = [b['name'] for b in all_benchmarks]
    
    result = await download_multiple_benchmarks(
        benchmark_names=benchmark_names,
        force_redownload=force_redownload
    )
    
    return {
        **result,
        'total_benchmarks': len(benchmark_names),
        'message': f'开始下载所有 {len(benchmark_names)} 个基准测试'
    }


@router.get("/benchmarks/{benchmark_name}/status", response_model=schemas.BenchmarkStatus)
async def get_benchmark_status_endpoint(
    benchmark_name: str
):
    """获取单个benchmark的缓存状态"""
    status = get_benchmark_status(benchmark_name)
    
    if not status:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_name}' 不存在")
    
    return status


@router.get("/benchmarks/{benchmark_name}/subsets/{subset_name}/samples")
async def get_subset_samples(
    benchmark_name: str,
    subset_name: str,
    limit: int = 5
):
    """获取子集的题目样本"""
    try:
        from datasets import load_dataset
        
        # 数据集配置映射
        dataset_mapping = {
            'mmlu': 'cais/mmlu',
            'cmmlu': 'cmmlu/cmmlu',
            'ceval': 'ceval/ceval',
            'gsm8k': 'gsm8k/gsm8k',
            'competition_math': 'hendrycks/competition_math',
            'arc': 'allenai/ai2_arc',
            'hellaswag': 'Rowan/hellaswag',
            'bbh': 'suzgun/bbh',
            'drop': 'drop',
            'race': 'ehovy/race',
            'alpaca_eval': 'tatsu-lab/alpaca_eval',
            'mmmu': 'mmmu/mmmu'
        }
        
        if benchmark_name not in dataset_mapping:
            raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_name}' 不支持样本查看")
        
        dataset_id = dataset_mapping[benchmark_name]
        
        # 加载数据集
        if benchmark_name in ['mmlu', 'cmmlu', 'ceval', 'race']:
            # 这些数据集有子集
            dataset = load_dataset(dataset_id, subset_name, split='test')
        else:
            # 其他数据集没有子集或使用默认配置
            dataset = load_dataset(dataset_id, split='test')
        
        # 获取样本
        samples = []
        for i in range(min(limit, len(dataset))):
            sample = dataset[i]
            samples.append({
                'index': i,
                'question': sample.get('question', sample.get('input', '')),
                'choices': sample.get('choices', []),
                'answer': sample.get('answer', sample.get('target', '')),
                'subject': sample.get('subject', subset_name),
                'raw_data': sample
            })
        
        return {
            'benchmark_name': benchmark_name,
            'subset_name': subset_name,
            'total_samples': len(dataset),
            'returned_samples': len(samples),
            'samples': samples
        }
        
    except Exception as e:
        logger.error(f"获取子集样本失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取子集样本失败: {str(e)}")


@router.get("/benchmarks/{benchmark_name}/subsets")
async def get_benchmark_subsets(
    benchmark_name: str
):
    """获取benchmark的子集详情"""
    # 数据集配置映射（包含子集详情）
    dataset_configs = {
        'gsm8k': {
            'subsets': ['main'], 
            'subset_details': {
                'main': {'name': '主要测试集', 'description': 'GSM8K小学数学应用题集合', 'category': '数学'}
            }
        },
        'math_500': {
            'subsets': ['Level 1', 'Level 2', 'Level 3', 'Level 4', 'Level 5'], 
            'subset_details': {
                'Level 1': {'name': 'Level 1', 'description': '基础数学问题', 'category': '基础'},
                'Level 2': {'name': 'Level 2', 'description': '初级数学问题', 'category': '初级'},
                'Level 3': {'name': 'Level 3', 'description': '中级数学问题', 'category': '中级'},
                'Level 4': {'name': 'Level 4', 'description': '高级数学问题', 'category': '高级'},
                'Level 5': {'name': 'Level 5', 'description': '专家级数学问题', 'category': '专家'}
            }
        },
        'competition_math': {
            'subsets': ['Level 1', 'Level 2', 'Level 3', 'Level 4', 'Level 5'], 
            'subset_details': {
                'Level 1': {'name': 'Level 1', 'description': '基础竞赛数学', 'category': '基础'},
                'Level 2': {'name': 'Level 2', 'description': '初级竞赛数学', 'category': '初级'},
                'Level 3': {'name': 'Level 3', 'description': '中级竞赛数学', 'category': '中级'},
                'Level 4': {'name': 'Level 4', 'description': '高级竞赛数学', 'category': '高级'},
                'Level 5': {'name': 'Level 5', 'description': '专家级竞赛数学', 'category': '专家'}
            }
        },
        'mmlu': {
            'subsets': [
                'abstract_algebra', 'anatomy', 'astronomy', 'business_ethics', 'clinical_knowledge',
                'college_biology', 'college_chemistry', 'college_computer_science', 'college_mathematics',
                'college_physics', 'college_medicine', 'computer_security', 'conceptual_physics',
                'econometrics', 'electrical_engineering', 'elementary_mathematics', 'formal_logic',
                'global_facts', 'high_school_biology', 'high_school_chemistry', 'high_school_computer_science',
                'high_school_european_history', 'high_school_geography', 'high_school_government_and_politics',
                'high_school_macroeconomics', 'high_school_mathematics', 'high_school_microeconomics',
                'high_school_physics', 'high_school_psychology', 'high_school_statistics', 'high_school_us_history',
                'high_school_world_history', 'human_aging', 'human_sexuality', 'international_law',
                'jurisprudence', 'logical_fallacies', 'machine_learning', 'management', 'marketing',
                'medical_genetics', 'miscellaneous', 'moral_disputes', 'moral_scenarios', 'nutrition',
                'philosophy', 'prehistory', 'professional_accounting', 'professional_law', 'professional_medicine',
                'professional_psychology', 'public_relations', 'security_studies', 'sociology', 'us_foreign_policy',
                'virology', 'world_religions'
            ],
            'subset_details': {
                'abstract_algebra': {'name': '抽象代数', 'description': '抽象代数概念和理论', 'category': '数学'},
                'anatomy': {'name': '解剖学', 'description': '人体解剖结构知识', 'category': '医学'},
                'astronomy': {'name': '天文学', 'description': '天体物理和宇宙学', 'category': '科学'},
                'business_ethics': {'name': '商业伦理', 'description': '商业道德和伦理问题', 'category': '商业'},
                'clinical_knowledge': {'name': '临床知识', 'description': '临床医学知识', 'category': '医学'},
                'college_biology': {'name': '大学生物学', 'description': '大学生物学课程内容', 'category': '生物'},
                'college_chemistry': {'name': '大学化学', 'description': '大学化学课程内容', 'category': '化学'},
                'college_computer_science': {'name': '大学计算机科学', 'description': '计算机科学基础', 'category': '计算机'},
                'college_mathematics': {'name': '大学数学', 'description': '高等数学内容', 'category': '数学'},
                'college_physics': {'name': '大学物理', 'description': '大学物理课程内容', 'category': '物理'},
                'college_medicine': {'name': '大学医学', 'description': '医学教育内容', 'category': '医学'},
                'computer_security': {'name': '计算机安全', 'description': '网络安全和信息安全', 'category': '计算机'},
                'conceptual_physics': {'name': '概念物理', 'description': '物理概念理解', 'category': '物理'},
                'econometrics': {'name': '计量经济学', 'description': '经济数据分析方法', 'category': '经济'},
                'electrical_engineering': {'name': '电气工程', 'description': '电气工程基础知识', 'category': '工程'},
                'elementary_mathematics': {'name': '初等数学', 'description': '基础数学知识', 'category': '数学'},
                'formal_logic': {'name': '形式逻辑', 'description': '逻辑推理和论证', 'category': '逻辑'},
                'global_facts': {'name': '全球事实', 'description': '世界地理和历史知识', 'category': '地理'},
                'high_school_biology': {'name': '高中生物学', 'description': '高中生物课程', 'category': '生物'},
                'high_school_chemistry': {'name': '高中化学', 'description': '高中化学课程', 'category': '化学'},
                'high_school_computer_science': {'name': '高中计算机科学', 'description': '高中计算机课程', 'category': '计算机'},
                'high_school_european_history': {'name': '高中欧洲历史', 'description': '欧洲历史知识', 'category': '历史'},
                'high_school_geography': {'name': '高中地理', 'description': '地理知识', 'category': '地理'},
                'high_school_government_and_politics': {'name': '高中政府与政治', 'description': '政治制度知识', 'category': '政治'},
                'high_school_macroeconomics': {'name': '高中宏观经济学', 'description': '宏观经济概念', 'category': '经济'},
                'high_school_mathematics': {'name': '高中数学', 'description': '高中数学课程', 'category': '数学'},
                'high_school_microeconomics': {'name': '高中微观经济学', 'description': '微观经济概念', 'category': '经济'},
                'high_school_physics': {'name': '高中物理', 'description': '高中物理课程', 'category': '物理'},
                'high_school_psychology': {'name': '高中心理学', 'description': '心理学基础知识', 'category': '心理'},
                'high_school_statistics': {'name': '高中统计学', 'description': '统计学基础', 'category': '数学'},
                'high_school_us_history': {'name': '高中美国历史', 'description': '美国历史知识', 'category': '历史'},
                'high_school_world_history': {'name': '高中世界历史', 'description': '世界历史知识', 'category': '历史'},
                'human_aging': {'name': '人类衰老', 'description': '衰老生物学知识', 'category': '生物'},
                'human_sexuality': {'name': '人类性学', 'description': '性学相关知识', 'category': '医学'},
                'international_law': {'name': '国际法', 'description': '国际法律知识', 'category': '法律'},
                'jurisprudence': {'name': '法理学', 'description': '法律哲学理论', 'category': '法律'},
                'logical_fallacies': {'name': '逻辑谬误', 'description': '逻辑推理错误识别', 'category': '逻辑'},
                'machine_learning': {'name': '机器学习', 'description': '机器学习算法', 'category': '计算机'},
                'management': {'name': '管理学', 'description': '管理理论和实践', 'category': '管理'},
                'marketing': {'name': '市场营销', 'description': '市场营销策略', 'category': '商业'},
                'medical_genetics': {'name': '医学遗传学', 'description': '遗传学在医学中的应用', 'category': '医学'},
                'miscellaneous': {'name': '杂项', 'description': '其他学科知识', 'category': '其他'},
                'moral_disputes': {'name': '道德争议', 'description': '道德伦理争议问题', 'category': '伦理'},
                'moral_scenarios': {'name': '道德情境', 'description': '道德判断情境', 'category': '伦理'},
                'nutrition': {'name': '营养学', 'description': '营养和健康知识', 'category': '医学'},
                'philosophy': {'name': '哲学', 'description': '哲学思想和理论', 'category': '哲学'},
                'prehistory': {'name': '史前史', 'description': '史前文明知识', 'category': '历史'},
                'professional_accounting': {'name': '专业会计', 'description': '会计专业知识', 'category': '商业'},
                'professional_law': {'name': '专业法律', 'description': '法律专业知识', 'category': '法律'},
                'professional_medicine': {'name': '专业医学', 'description': '医学专业知识', 'category': '医学'},
                'professional_psychology': {'name': '专业心理学', 'description': '心理学专业知识', 'category': '心理'},
                'public_relations': {'name': '公共关系', 'description': '公关理论和实践', 'category': '商业'},
                'security_studies': {'name': '安全研究', 'description': '安全政策和战略', 'category': '政治'},
                'sociology': {'name': '社会学', 'description': '社会结构和行为', 'category': '社会'},
                'us_foreign_policy': {'name': '美国外交政策', 'description': '美国外交政策知识', 'category': '政治'},
                'virology': {'name': '病毒学', 'description': '病毒和传染病知识', 'category': '医学'},
                'world_religions': {'name': '世界宗教', 'description': '世界主要宗教知识', 'category': '宗教'}
            }
        },
        'arc': {
            'subsets': ['challenge', 'easy'], 
            'subset_details': {
                'challenge': {'name': '挑战集', 'description': 'ARC挑战级科学推理问题', 'category': '挑战'},
                'easy': {'name': '简单集', 'description': 'ARC简单级科学推理问题', 'category': '简单'}
            }
        },
        'cmmlu': {
            'subsets': [
                'agronomy', 'anatomy', 'ancient_chinese_history', 'arts', 'basic_medicine', 'business_administration',
                'chinese_civil_service', 'chinese_driving_rule', 'chinese_food_culture', 'chinese_literature',
                'chinese_teacher_qualification', 'civil_servant', 'computer_science', 'computer_network',
                'discrete_mathematics', 'education_science', 'electrical_engineer', 'fire_engineer',
                'ideological_and_moral_cultivation', 'law', 'logic', 'mao_zedong_thought', 'marxism',
                'metrology_engineer', 'middle_school_biology', 'middle_school_chemistry', 'middle_school_geography',
                'middle_school_history', 'middle_school_mathematics', 'middle_school_physics', 'middle_school_politics',
                'operating_system', 'physician', 'plant_protection', 'probability_and_statistics', 'professional_tour_guide',
                'sports', 'tax_accountant', 'teacher_qualification', 'urban_and_rural_planner', 'veterinarian'
            ],
            'subset_details': {
                'agronomy': {'name': '农学', 'description': '农业科学知识', 'category': '农业'},
                'anatomy': {'name': '解剖学', 'description': '人体解剖结构', 'category': '医学'},
                'ancient_chinese_history': {'name': '中国古代史', 'description': '中国古代历史', 'category': '历史'},
                'arts': {'name': '艺术', 'description': '艺术理论和实践', 'category': '艺术'},
                'basic_medicine': {'name': '基础医学', 'description': '医学基础知识', 'category': '医学'},
                'business_administration': {'name': '工商管理', 'description': '企业管理知识', 'category': '管理'},
                'chinese_civil_service': {'name': '中国公务员', 'description': '公务员制度知识', 'category': '政治'},
                'chinese_driving_rule': {'name': '中国驾驶规则', 'description': '交通法规知识', 'category': '交通'},
                'chinese_food_culture': {'name': '中国饮食文化', 'description': '中华饮食文化', 'category': '文化'},
                'chinese_literature': {'name': '中国文学', 'description': '中国文学知识', 'category': '文学'},
                'chinese_teacher_qualification': {'name': '中国教师资格', 'description': '教师资格考试', 'category': '教育'},
                'civil_servant': {'name': '公务员', 'description': '公务员考试知识', 'category': '政治'},
                'computer_science': {'name': '计算机科学', 'description': '计算机科学基础', 'category': '计算机'},
                'computer_network': {'name': '计算机网络', 'description': '网络技术知识', 'category': '计算机'},
                'discrete_mathematics': {'name': '离散数学', 'description': '离散数学理论', 'category': '数学'},
                'education_science': {'name': '教育学', 'description': '教育理论和实践', 'category': '教育'},
                'electrical_engineer': {'name': '电气工程师', 'description': '电气工程知识', 'category': '工程'},
                'fire_engineer': {'name': '消防工程师', 'description': '消防安全知识', 'category': '工程'},
                'ideological_and_moral_cultivation': {'name': '思想道德修养', 'description': '思想道德教育', 'category': '政治'},
                'law': {'name': '法律', 'description': '法律基础知识', 'category': '法律'},
                'logic': {'name': '逻辑学', 'description': '逻辑推理知识', 'category': '逻辑'},
                'mao_zedong_thought': {'name': '毛泽东思想', 'description': '毛泽东思想理论', 'category': '政治'},
                'marxism': {'name': '马克思主义', 'description': '马克思主义理论', 'category': '政治'},
                'metrology_engineer': {'name': '计量工程师', 'description': '计量技术知识', 'category': '工程'},
                'middle_school_biology': {'name': '初中生物学', 'description': '初中生物课程', 'category': '生物'},
                'middle_school_chemistry': {'name': '初中化学', 'description': '初中化学课程', 'category': '化学'},
                'middle_school_geography': {'name': '初中地理', 'description': '初中地理课程', 'category': '地理'},
                'middle_school_history': {'name': '初中历史', 'description': '初中历史课程', 'category': '历史'},
                'middle_school_mathematics': {'name': '初中数学', 'description': '初中数学课程', 'category': '数学'},
                'middle_school_physics': {'name': '初中物理', 'description': '初中物理课程', 'category': '物理'},
                'middle_school_politics': {'name': '初中政治', 'description': '初中政治课程', 'category': '政治'},
                'operating_system': {'name': '操作系统', 'description': '操作系统原理', 'category': '计算机'},
                'physician': {'name': '医师', 'description': '医师资格考试', 'category': '医学'},
                'plant_protection': {'name': '植物保护', 'description': '植物保护知识', 'category': '农业'},
                'probability_and_statistics': {'name': '概率统计', 'description': '概率论和统计学', 'category': '数学'},
                'professional_tour_guide': {'name': '专业导游', 'description': '导游专业知识', 'category': '旅游'},
                'sports': {'name': '体育', 'description': '体育科学知识', 'category': '体育'},
                'tax_accountant': {'name': '税务会计师', 'description': '税务会计知识', 'category': '会计'},
                'teacher_qualification': {'name': '教师资格', 'description': '教师资格考试', 'category': '教育'},
                'urban_and_rural_planner': {'name': '城乡规划师', 'description': '城乡规划知识', 'category': '规划'},
                'veterinarian': {'name': '兽医', 'description': '兽医学知识', 'category': '医学'}
            }
        },
        'race': {
            'subsets': ['all', 'high', 'middle'],
            'subset_details': {
                'all': {'name': '全部', 'description': 'RACE完整阅读理解数据集', 'category': '阅读理解'},
                'high': {'name': '高中', 'description': 'RACE高中阅读理解题目', 'category': '阅读理解'},
                'middle': {'name': '初中', 'description': 'RACE初中阅读理解题目', 'category': '阅读理解'}
            }
        },
        'hellaswag': {
            'subsets': ['main'],
            'subset_details': {
                'main': {'name': '主要测试集', 'description': 'HellaSwag常识推理数据集', 'category': '常识推理'}
            }
        },
        'bbh': {
            'subsets': ['main'],
            'subset_details': {
                'main': {'name': '主要测试集', 'description': 'BBH困难推理基准测试', 'category': '困难推理'}
            }
        },
        'drop': {
            'subsets': ['main'],
            'subset_details': {
                'main': {'name': '主要测试集', 'description': 'DROP阅读理解数据集', 'category': '阅读理解'}
            }
        },
        'alpaca_eval': {
            'subsets': ['main'],
            'subset_details': {
                'main': {'name': '主要测试集', 'description': 'AlpacaEval对话评估数据集', 'category': '对话能力'}
            }
        },
        'mmmu': {
            'subsets': ['main'],
            'subset_details': {
                'main': {'name': '主要测试集', 'description': 'MMMU多模态理解数据集', 'category': '多模态理解'}
            }
        },
        'ceval': {
            'subsets': [
                'computer_architecture', 'computer_network', 'computer_organization', 'discrete_mathematics',
                'fire_engineer', 'ideological_and_moral_cultivation', 'marxism', 'mao_zedong_thought',
                'operating_system', 'probability_and_statistics', 'advanced_mathematics', 'art_studies',
                'basic_medicine', 'business_administration', 'chinese_civil_service', 'chinese_literature',
                'college_chemistry', 'college_economics', 'college_physics', 'college_programming',
                'computer_science', 'data_structure', 'educator', 'fire_safety', 'ideological_and_moral_cultivation',
                'logic', 'mao_zedong_thought', 'marxism', 'metrology_engineer', 'middle_school_biology',
                'middle_school_chemistry', 'middle_school_geography', 'middle_school_history', 'middle_school_mathematics',
                'middle_school_physics', 'middle_school_politics', 'modern_chinese_history', 'operating_system',
                'physician', 'plant_protection', 'probability_and_statistics', 'professional_tour_guide',
                'sports', 'tax_accountant', 'teacher_qualification', 'urban_and_rural_planner', 'veterinarian'
            ],
            'subset_details': {
                'computer_architecture': {'name': '计算机体系结构', 'description': '计算机硬件架构', 'category': '计算机'},
                'computer_network': {'name': '计算机网络', 'description': '网络技术知识', 'category': '计算机'},
                'computer_organization': {'name': '计算机组成', 'description': '计算机硬件组成', 'category': '计算机'},
                'discrete_mathematics': {'name': '离散数学', 'description': '离散数学理论', 'category': '数学'},
                'fire_engineer': {'name': '消防工程师', 'description': '消防安全知识', 'category': '工程'},
                'ideological_and_moral_cultivation': {'name': '思想道德修养', 'description': '思想道德教育', 'category': '政治'},
                'marxism': {'name': '马克思主义', 'description': '马克思主义理论', 'category': '政治'},
                'mao_zedong_thought': {'name': '毛泽东思想', 'description': '毛泽东思想理论', 'category': '政治'},
                'operating_system': {'name': '操作系统', 'description': '操作系统原理', 'category': '计算机'},
                'probability_and_statistics': {'name': '概率统计', 'description': '概率论和统计学', 'category': '数学'},
                'advanced_mathematics': {'name': '高等数学', 'description': '高等数学内容', 'category': '数学'},
                'art_studies': {'name': '艺术学', 'description': '艺术理论和实践', 'category': '艺术'},
                'basic_medicine': {'name': '基础医学', 'description': '医学基础知识', 'category': '医学'},
                'business_administration': {'name': '工商管理', 'description': '企业管理知识', 'category': '管理'},
                'chinese_civil_service': {'name': '中国公务员', 'description': '公务员制度知识', 'category': '政治'},
                'chinese_literature': {'name': '中国文学', 'description': '中国文学知识', 'category': '文学'},
                'college_chemistry': {'name': '大学化学', 'description': '大学化学课程', 'category': '化学'},
                'college_economics': {'name': '大学经济学', 'description': '经济学理论', 'category': '经济'},
                'college_physics': {'name': '大学物理', 'description': '大学物理课程', 'category': '物理'},
                'college_programming': {'name': '大学编程', 'description': '编程基础知识', 'category': '计算机'},
                'computer_science': {'name': '计算机科学', 'description': '计算机科学基础', 'category': '计算机'},
                'data_structure': {'name': '数据结构', 'description': '数据结构算法', 'category': '计算机'},
                'educator': {'name': '教育者', 'description': '教育专业知识', 'category': '教育'},
                'fire_safety': {'name': '消防安全', 'description': '消防安全知识', 'category': '安全'},
                'logic': {'name': '逻辑学', 'description': '逻辑推理知识', 'category': '逻辑'},
                'metrology_engineer': {'name': '计量工程师', 'description': '计量技术知识', 'category': '工程'},
                'middle_school_biology': {'name': '初中生物学', 'description': '初中生物课程', 'category': '生物'},
                'middle_school_chemistry': {'name': '初中化学', 'description': '初中化学课程', 'category': '化学'},
                'middle_school_geography': {'name': '初中地理', 'description': '初中地理课程', 'category': '地理'},
                'middle_school_history': {'name': '初中历史', 'description': '初中历史课程', 'category': '历史'},
                'middle_school_mathematics': {'name': '初中数学', 'description': '初中数学课程', 'category': '数学'},
                'middle_school_physics': {'name': '初中物理', 'description': '初中物理课程', 'category': '物理'},
                'middle_school_politics': {'name': '初中政治', 'description': '初中政治课程', 'category': '政治'},
                'modern_chinese_history': {'name': '中国近现代史', 'description': '中国近现代历史', 'category': '历史'},
                'physician': {'name': '医师', 'description': '医师资格考试', 'category': '医学'},
                'plant_protection': {'name': '植物保护', 'description': '植物保护知识', 'category': '农业'},
                'professional_tour_guide': {'name': '专业导游', 'description': '导游专业知识', 'category': '旅游'},
                'sports': {'name': '体育', 'description': '体育科学知识', 'category': '体育'},
                'tax_accountant': {'name': '税务会计师', 'description': '税务会计知识', 'category': '会计'},
                'teacher_qualification': {'name': '教师资格', 'description': '教师资格考试', 'category': '教育'},
                'urban_and_rural_planner': {'name': '城乡规划师', 'description': '城乡规划知识', 'category': '规划'},
                'veterinarian': {'name': '兽医', 'description': '兽医学知识', 'category': '医学'}
            }
        }
    }
    
    if benchmark_name not in dataset_configs:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_name}' 的子集信息不存在")
    
    config = dataset_configs[benchmark_name]
    subsets = config['subsets']
    subset_details = config.get('subset_details', {})
    
    # 构建子集详情列表
    subset_list = []
    for subset in subsets:
        detail = subset_details.get(subset, {})
        subset_list.append({
            'id': subset,
            'name': detail.get('name', subset),
            'description': detail.get('description', f'{subset} 子集'),
            'category': detail.get('category', '其他')
        })
    
    return {
        'benchmark_name': benchmark_name,
        'total_subsets': len(subsets),
        'subsets': subset_list
    }


@router.post("/tasks/{task_id}/validate-model")
async def validate_task_model(
    task_id: int,
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """验证任务中使用的模型是否仍然存在"""
    # 获取任务
    task = await EvalScopeService.get_task(db=db, task_id=task_id, user_id=None)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查模型是否存在 - 真正查询可用模型列表
    model_service = UnifiedModelService(db)
    
    model_id = task.model_id
    model_exists = False
    model_info = None
    
    if model_id:
        # 方法1：检查是否是用户配置的模型
        if model_id.startswith('user_config_'):
            try:
                config_id = model_id.replace('user_config_', '')
                from app.models.user_config import UserModelConfig
                user_config = db.query(UserModelConfig).filter(
                    UserModelConfig.id == config_id,
                    UserModelConfig.is_active == True
                ).first()
                
                if user_config:
                    model_exists = True
                    model_info = {
                        "id": model_id,
                        "name": user_config.model_name,
                        "display_name": user_config.name,
                        "type": "user_config"
                    }
            except Exception as e:
                print(f"查询用户配置模型时出错: {e}")
                model_exists = False
        
        # 方法2：在所有用户的可用模型中查找
        if not model_exists:
            try:
                # 获取所有用户的可用模型进行匹配
                from app.models.model_management import ModelInfo
                from app.models.user_config import UserModelConfig
                from app.models.model_config import ModelConfig
                
                # 查询ModelInfo表
                model_info_record = db.query(ModelInfo).filter(
                    ModelInfo.model_id == model_id,
                    ModelInfo.is_active == True,
                    ModelInfo.status == 'available'
                ).first()
                
                if model_info_record:
                    model_exists = True
                    model_info = {
                        "id": model_info_record.model_id,
                        "name": model_info_record.model_name,
                        "display_name": model_info_record.display_name or model_info_record.model_name,
                        "type": model_info_record.model_type
                    }
                else:
                    # 查询UserModelConfig表（按模型名称匹配）
                    user_model_configs = db.query(UserModelConfig).filter(
                        UserModelConfig.model_name == model_id,
                        UserModelConfig.is_active == True
                    ).all()
                    
                    if user_model_configs:
                        model_exists = True
                        config = user_model_configs[0]  # 取第一个匹配的配置
                        model_info = {
                            "id": f"user_config_{config.id}",
                            "name": config.model_name,
                            "display_name": config.name,
                            "type": "user_config"
                        }
                    else:
                        # 查询ModelConfig表（传统配置）
                        model_configs = db.query(ModelConfig).filter(
                            ModelConfig.model_name == model_id,
                            ModelConfig.is_active == True
                        ).all()
                        
                        if model_configs:
                            model_exists = True
                            config = model_configs[0]
                            model_info = {
                                "id": f"model_config_{config.id}",
                                "name": config.model_name or config.model_id,
                                "display_name": config.model_name or config.model_id,
                                "type": "local" if config.model_path else "api"
                            }
                        
            except Exception as e:
                print(f"查询模型时出错: {e}")
                model_exists = False
    
    return {
        "task_id": task_id,
        "model_id": model_id,
        "model_exists": model_exists,
        "model_info": model_info,
        "can_retry": model_exists and task.status in ['failed', 'cancelled']
    }


# ==================== WebSocket实时通信 ====================

@router.websocket("/ws/tasks/{task_id}")
async def websocket_task_progress(
    websocket: WebSocket,
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """WebSocket实时进度推送"""
    await ws_manager.connect(task_id, websocket)
    
    try:
        while True:
            # 保持连接，接收客户端消息（可选）
            data = await websocket.receive_text()
            
            # 可以处理客户端发送的消息，例如心跳
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        ws_manager.disconnect(task_id, websocket)


@router.post("/tasks/check-stuck")
async def check_stuck_tasks_endpoint(
    timeout_minutes: int = 30
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """检查并修复卡住的任务（临时移除认证）"""
    fixed_task_ids = check_stuck_tasks(timeout_minutes=timeout_minutes)
    
    return {
        "success": True,
        "fixed_count": len(fixed_task_ids),
        "fixed_task_ids": fixed_task_ids,
        "message": f"检查完成，修复了 {len(fixed_task_ids)} 个卡住的任务"
    }


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(
    request: TranslateRequest,
    db: Session = Depends(deps.get_db)
    # 临时移除认证: current_user: User = Depends(deps.get_current_user)
):
    """翻译文本"""
    try:
        text = request.text.strip()
        target_lang = request.target_lang
        
        if not text:
            return TranslateResponse(translated_text="")
        
        # 使用已配置的大模型进行翻译
        try:
            # 尝试导入LLM翻译服务
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
            from llm_translation_service import translate_text_with_llm
            
            # 使用指定的翻译模型进行翻译
            translated_text = translate_text_with_llm(text, target_lang, db_session=db)
            
        except ImportError:
            # 如果翻译服务不可用，使用简单的回退方案
            logger.warning("翻译服务不可用，使用简单回退方案")
            
            # 检测是否包含中文字符
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)
            
            if not has_chinese and target_lang == "zh":
                # 简单的关键词替换
                translations = {
                    "benchmark": "基准测试",
                    "dataset": "数据集", 
                    "evaluates": "评估",
                    "tests": "测试",
                    "comprehensive": "全面的",
                    "large-scale": "大规模的",
                    "performance": "性能",
                    "reasoning": "推理",
                    "comprehension": "理解",
                    "generation": "生成",
                    "understanding": "理解",
                    "knowledge": "知识",
                    "scientific": "科学的",
                    "technical": "技术的",
                    "commonsense": "常识",
                    "creative": "创意的",
                    "writing": "写作",
                    "academic": "学术的",
                    "subjects": "学科",
                    "capabilities": "能力",
                    "tasks": "任务",
                    "domains": "领域"
                }
                
                translated_text = text
                for en_word, zh_word in translations.items():
                    translated_text = translated_text.replace(en_word, zh_word)
                    translated_text = translated_text.replace(en_word.capitalize(), zh_word)
                    translated_text = translated_text.replace(en_word.upper(), zh_word)
                
                # 如果翻译结果和原文相同，添加前缀
                if translated_text == text:
                    translated_text = f"描述：{text}"
            else:
                translated_text = text
        
        return TranslateResponse(translated_text=translated_text)
        
    except Exception as e:
        logger.error(f"翻译失败: {e}")
        raise HTTPException(status_code=500, detail=f"翻译失败: {str(e)}")


@router.get("/tasks/{task_id}/json-reports")
async def get_task_json_reports(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """获取任务的JSON报告文件"""
    try:
        # 查找任务对应的输出目录
        outputs_dir = Path("outputs")
        task_dir = outputs_dir / f"evalscope_task_{task_id}"
        
        if not task_dir.exists():
            raise HTTPException(status_code=404, detail="任务输出目录不存在")
        
        # 查找所有JSON报告文件
        json_reports = []
        for report_file in task_dir.glob("**/reports/**/*.json"):
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                json_reports.append(report_data)
            except Exception as e:
                print(f"读取报告文件失败: {report_file}, 错误: {e}")
                continue
        
        if not json_reports:
            raise HTTPException(status_code=404, detail="未找到JSON报告文件")
        
        return json_reports
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取JSON报告失败: {str(e)}")


@router.post("/tasks/{task_id}/import-results")
async def import_task_results_from_json(
    task_id: int,
    db: Session = Depends(deps.get_db)
):
    """从JSON报告文件导入结果到数据库（用于修复丢失的结果）"""
    try:
        # 查找任务
        task = db.query(EvalScopeTask).filter(EvalScopeTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 查找任务对应的输出目录
        outputs_dir = Path("outputs")
        task_dir = outputs_dir / f"evalscope_task_{task_id}"
        
        if not task_dir.exists():
            raise HTTPException(status_code=404, detail="任务输出目录不存在")
        
        imported_count = 0
        skipped_count = 0
        
        # 查找所有JSON报告文件
        for report_file in task_dir.glob("**/reports/**/*.json"):
            try:
                with open(report_file, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                
                dataset_name = report_data.get('dataset_name')
                if not dataset_name:
                    continue
                
                # 检查该数据集的结果是否已存在
                existing = db.query(EvalScopeResult).filter(
                    EvalScopeResult.task_id == task_id,
                    EvalScopeResult.benchmark == dataset_name
                ).first()
                
                if existing:
                    print(f"数据集 {dataset_name} 的结果已存在，跳过")
                    skipped_count += 1
                    continue
                
                # 解析并保存结果
                metrics = report_data.get('metrics', [])
                for metric in metrics:
                    metric_name = metric.get('name', 'accuracy')
                    categories = metric.get('categories', [])
                    
                    if categories:
                        for category in categories:
                            category_name = category.get('name', ['default'])
                            if isinstance(category_name, list):
                                category_name = category_name[0] if category_name else 'default'
                            
                            subsets = category.get('subsets', [])
                            if subsets:
                                for subset in subsets:
                                    result = EvalScopeResult(
                                        task_id=task_id,
                                        benchmark=dataset_name,
                                        metric_name=metric_name,
                                        metric_value=float(subset.get('score', 0)),
                                        category=category_name,
                                        subset_name=subset.get('name', 'main'),
                                        num_samples=subset.get('num'),
                                        raw_results={
                                            'benchmark': dataset_name,
                                            'metric_name': metric_name,
                                            'metric_value': float(subset.get('score', 0)),
                                            'category': category_name,
                                            'subset_name': subset.get('name', 'main'),
                                            'num_samples': subset.get('num')
                                        }
                                    )
                                    db.add(result)
                                    imported_count += 1
                            else:
                                # 没有子集，使用类别级别数据
                                result = EvalScopeResult(
                                    task_id=task_id,
                                    benchmark=dataset_name,
                                    metric_name=metric_name,
                                    metric_value=float(category.get('score', 0)),
                                    category=category_name,
                                    subset_name='main',
                                    num_samples=category.get('num'),
                                    raw_results={
                                        'benchmark': dataset_name,
                                        'metric_name': metric_name,
                                        'metric_value': float(category.get('score', 0)),
                                        'category': category_name,
                                        'subset_name': 'main',
                                        'num_samples': category.get('num')
                                    }
                                )
                                db.add(result)
                                imported_count += 1
                    else:
                        # 没有类别，使用指标级别数据
                        result = EvalScopeResult(
                            task_id=task_id,
                            benchmark=dataset_name,
                            metric_name=metric_name,
                            metric_value=float(metric.get('score', 0)),
                            category='default',
                            subset_name='main',
                            num_samples=metric.get('num'),
                            raw_results={
                                'benchmark': dataset_name,
                                'metric_name': metric_name,
                                'metric_value': float(metric.get('score', 0)),
                                'category': 'default',
                                'subset_name': 'main',
                                'num_samples': metric.get('num')
                            }
                        )
                        db.add(result)
                        imported_count += 1
                
            except Exception as e:
                print(f"导入报告文件失败: {report_file}, 错误: {e}")
                continue
        
        # 提交事务
        db.commit()
        
        return {
            "success": True,
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "message": f"成功导入 {imported_count} 条结果，跳过 {skipped_count} 个已存在的数据集"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"导入结果失败: {str(e)}")


# 导出ws_manager供其他模块使用
__all__ = ['router', 'ws_manager']

