"""
EvalScope评测API端点
"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import asyncio

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

router = APIRouter()

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
        # 使用优化版本的任务
        try:
            from app.tasks.evalscope_tasks_optimized import run_real_evaluation_task, CELERY_AVAILABLE
            evaluation_task = run_real_evaluation_task
            use_fixed = False
            print(f"✅ 使用优化版本任务，CELERY_AVAILABLE: {CELERY_AVAILABLE}")
        except ImportError as e:
            print(f"❌ 优化版本导入失败: {e}")
            # 回退到原版本
            try:
                from app.tasks.evalscope_tasks_real import run_real_evaluation_task, CELERY_AVAILABLE
                evaluation_task = run_real_evaluation_task
                use_fixed = False
                print(f"✅ 使用原版本任务，CELERY_AVAILABLE: {CELERY_AVAILABLE}")
            except ImportError as e2:
                print(f"❌ 原版本导入失败: {e2}")
                raise HTTPException(
                    status_code=500,
                    detail="所有评测任务模块都无法导入，请检查Celery配置"
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
    
    return task


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
            last_updated=b.get('last_updated')
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


# 导出ws_manager供其他模块使用
__all__ = ['router', 'ws_manager']

