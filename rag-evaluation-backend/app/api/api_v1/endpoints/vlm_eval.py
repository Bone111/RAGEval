from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app import schemas
from app.api import deps
from app.models.vlm_task import VLMTask, VLMResult
from app.db.base import SessionLocal

router = APIRouter()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/datasets", response_model=List[schemas.VLMDatasetInfo])
async def get_vlm_datasets():
    """获取支持的VLM数据集列表"""
    # 返回真实的VLMEval支持的数据集信息（基于EvalScope VLMEval框架）
    datasets = [
        {
            "name": "MMBench_DEV_EN",
            "display_name": "MMBench Development (English)", 
            "description": "Multi-modal benchmark for perception and reasoning",
            "category": "综合理解",
            "language": "en",
            "num_samples": 2974,
            "supported_metrics": ["accuracy", "score"]
        },
        {
            "name": "MMBench_DEV_CN",
            "display_name": "MMBench Development (Chinese)",
            "description": "Multi-modal benchmark for perception and reasoning (Chinese)",
            "category": "综合理解", 
            "language": "zh",
            "num_samples": 2974,
            "supported_metrics": ["accuracy", "score"]
        },
        {
            "name": "MME",
            "display_name": "MME Benchmark",
            "description": "Multi-modal evaluation benchmark for perception and cognition",
            "category": "感知推理",
            "language": "en", 
            "num_samples": 2374,
            "supported_metrics": ["accuracy", "perception_score", "cognition_score"]
        },
        {
            "name": "SEEDBench_IMG",
            "display_name": "SEED-Bench Image",
            "description": "Benchmarking multimodal LLMs with generative comprehension",
            "category": "视觉理解",
            "language": "en",
            "num_samples": 19242,
            "supported_metrics": ["accuracy"]
        },
        {
            "name": "MMVet",
            "display_name": "MM-Vet", 
            "description": "Evaluating Large Multimodal Models for Integrated Capabilities",
            "category": "综合能力",
            "language": "en",
            "num_samples": 218,
            "supported_metrics": ["score"]
        },
        {
            "name": "MMMU_DEV_VAL",
            "display_name": "MMMU Development Validation",
            "description": "A Massive Multi-discipline Multimodal Understanding",
            "category": "学科知识", 
            "language": "en",
            "num_samples": 900,
            "supported_metrics": ["accuracy"]
        },
        {
            "name": "MathVista_MINI",
            "display_name": "MathVista Mini",
            "description": "Mathematical reasoning in visual contexts", 
            "category": "数学视觉",
            "language": "en",
            "num_samples": 1000,
            "supported_metrics": ["accuracy", "score"]
        },
        {
            "name": "OCRBench",
            "display_name": "OCRBench",
            "description": "A Comprehensive Evaluation of OCR for Multimodal Large Language Models",
            "category": "OCR识别",
            "language": "multi",
            "num_samples": 1000,
            "supported_metrics": ["accuracy", "word_accuracy", "edit_distance"]
        },
        {
            "name": "ChartQA_TEST", 
            "display_name": "ChartQA Test",
            "description": "A benchmark for question answering about charts",
            "category": "图表分析",
            "language": "en", 
            "num_samples": 2204,
            "supported_metrics": ["accuracy", "relaxed_accuracy"]
        },
        {
            "name": "AI2D_TEST",
            "display_name": "AI2D Test",
            "description": "A dataset for diagram understanding and question answering",
            "category": "图表理解",
            "language": "en",
            "num_samples": 3088,
            "supported_metrics": ["accuracy"]
        }
    ]
    return datasets


@router.get("/models", response_model=List[schemas.VLMModelInfo])
async def get_vlm_models():
    """获取支持的VLM模型列表"""
    # 返回真实的VLMEval支持的模型列表（基于EvalScope VLMEval框架）
    models = [
        {
            "name": "qwen-vl-chat",
            "display_name": "Qwen-VL-Chat",
            "description": "通义千问视觉语言模型",
            "model_type": "local",
            "supported_modalities": ["text", "image"],
            "max_tokens": 2048,
            "requires_api_key": False
        },
        {
            "name": "llava-v1.5-7b",
            "display_name": "LLaVA-1.5-7B", 
            "description": "Large Language and Vision Assistant",
            "model_type": "local",
            "supported_modalities": ["text", "image"],
            "max_tokens": 2048,
            "requires_api_key": False
        },
        {
            "name": "llava-v1.5-13b",
            "display_name": "LLaVA-1.5-13B",
            "description": "Large Language and Vision Assistant (13B)",
            "model_type": "local", 
            "supported_modalities": ["text", "image"],
            "max_tokens": 2048,
            "requires_api_key": False
        },
        {
            "name": "internlm-xcomposer2-vl-7b",
            "display_name": "InternLM-XComposer2-VL-7B",
            "description": "浦源多模态大模型",
            "model_type": "local",
            "supported_modalities": ["text", "image"],
            "max_tokens": 2048, 
            "requires_api_key": False
        },
        {
            "name": "blip2-opt-2.7b",
            "display_name": "BLIP2-OPT-2.7B",
            "description": "Salesforce BLIP2 multimodal model",
            "model_type": "local",
            "supported_modalities": ["text", "image"],
            "max_tokens": 1024,
            "requires_api_key": False
        },
        {
            "name": "custom-api",
            "display_name": "自定义API模型",
            "description": "通过API调用的自定义VLM模型",
            "model_type": "api",
            "supported_modalities": ["text", "image"],
            "max_tokens": 4096,
            "requires_api_key": True
        }
    ]
    return models


@router.post("/tasks", response_model=schemas.VLMTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_vlm_task(
    task_data: schemas.VLMTaskCreate,
    db: Session = Depends(get_db)
):
    """创建VLM评测任务"""
    # 临时使用固定用户ID
    test_user_id = "5bddb026-0a9d-4a87-8958-d97860566dc9"
    
    # 创建任务记录
    vlm_task = VLMTask(
        user_id=test_user_id,
        task_name=task_data.task_name,
        model_id=task_data.model_id,
        datasets=task_data.datasets,
        status="pending",
        progress=0,
        model_type=task_data.model_type,
        api_base=task_data.api_base,
        model_path=task_data.model_path,
        eval_backend=task_data.eval_backend,
        limit=task_data.limit,
        nproc=task_data.nproc or 1,
        temperature=task_data.temperature or 0.0,
        max_tokens=task_data.max_tokens or 1024,
        reuse_cache=task_data.reuse_cache or True,
        extra_config=task_data.extra_config,
        work_dir=f"./outputs/vlm_task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    )
    
    # 如果是API模型，不保存原始密钥
    if task_data.api_key:
        # 使用MD5哈希存储API密钥（注意：生产环境建议使用更强的加密方式）
        import hashlib
        vlm_task.api_key_hash = hashlib.md5(task_data.api_key.encode()).hexdigest()
    
    db.add(vlm_task)
    db.commit()
    db.refresh(vlm_task)
    
    # 启动VLM评测任务（使用Celery异步执行）
    try:
        from app.tasks.vlm_tasks import run_vlm_evaluation_task
        celery_task = run_vlm_evaluation_task.delay(vlm_task.id)
        vlm_task.celery_task_id = celery_task.id
        vlm_task.status = 'pending'
        db.commit()
    except ImportError:
        # 如果vlm_tasks模块不存在，保持pending状态
        vlm_task.status = 'pending'
        vlm_task.error_message = "VLM评测模块未实现，请先实现 app.tasks.vlm_tasks"
        db.commit()
    except Exception as e:
        vlm_task.status = 'failed'
        vlm_task.error_message = f"任务调度失败: {str(e)}"
        db.commit()
    
    return vlm_task


@router.get("/tasks", response_model=List[schemas.VLMTaskResponse])
async def get_vlm_tasks(
    status: Optional[str] = Query(None, description="任务状态过滤"),
    limit: int = Query(20, description="限制返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取VLM任务列表"""
    query = db.query(VLMTask)
    
    if status:
        query = query.filter(VLMTask.status == status)
    
    tasks = query.order_by(VLMTask.created_at.desc()).offset(offset).limit(limit).all()
    return tasks


@router.get("/tasks/{task_id}", response_model=schemas.VLMTaskDetail)
async def get_vlm_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """获取VLM任务详情"""
    task = db.query(VLMTask).filter(VLMTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="VLM任务不存在")
    
    return task


@router.get("/tasks/{task_id}/results", response_model=List[schemas.VLMResultResponse])
async def get_vlm_task_results(
    task_id: str,
    db: Session = Depends(get_db)
):
    """获取VLM任务结果"""
    task = db.query(VLMTask).filter(VLMTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="VLM任务不存在")
    
    # 直接返回真实的评测结果，不返回模拟数据
    results = db.query(VLMResult).filter(VLMResult.task_id == task_id).all()
    return results


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vlm_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """删除VLM任务"""
    task = db.query(VLMTask).filter(VLMTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="VLM任务不存在")
    
    # TODO: 取消正在运行的Celery任务
    
    db.delete(task)
    db.commit()


@router.post("/tasks/{task_id}/cancel", response_model=schemas.VLMTaskResponse)
async def cancel_vlm_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """取消VLM任务"""
    task = db.query(VLMTask).filter(VLMTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="VLM任务不存在")
    
    if task.status not in ['pending', 'running']:
        raise HTTPException(status_code=400, detail=f"任务状态为{task.status}，无法取消")
    
    # TODO: 取消Celery任务
    
    task.status = 'cancelled'
    task.completed_at = datetime.now(timezone.utc)
    db.commit()
    
    return task


@router.get("/stats", response_model=schemas.VLMTaskStats)
async def get_vlm_stats(
    db: Session = Depends(get_db)
):
    """获取VLM任务统计信息"""
    from sqlalchemy import func
    from datetime import timedelta
    
    total_tasks = db.query(VLMTask).count()
    running_tasks = db.query(VLMTask).filter(VLMTask.status == 'running').count()
    completed_tasks = db.query(VLMTask).filter(VLMTask.status == 'completed').count()
    failed_tasks = db.query(VLMTask).filter(VLMTask.status == 'failed').count()
    
    # 计算真实的平均执行时长（仅统计已完成的任务）
    avg_duration_minutes = None
    completed_with_time = db.query(VLMTask).filter(
        VLMTask.status == 'completed',
        VLMTask.started_at.isnot(None),
        VLMTask.completed_at.isnot(None)
    ).all()
    
    if completed_with_time:
        total_duration_seconds = sum([
            (task.completed_at - task.started_at).total_seconds()
            for task in completed_with_time
        ])
        avg_duration_minutes = round(total_duration_seconds / len(completed_with_time) / 60, 2)
    
    # 统计真实的热门数据集（从任务记录中统计）
    # 注意：datasets是JSON数组，需要特殊处理
    popular_datasets = []
    all_tasks = db.query(VLMTask).all()
    dataset_counts = {}
    for task in all_tasks:
        if task.datasets:
            for dataset in task.datasets:
                dataset_counts[dataset] = dataset_counts.get(dataset, 0) + 1
    
    # 取前3个最热门的数据集
    sorted_datasets = sorted(dataset_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    popular_datasets = [{"name": name, "usage_count": count} for name, count in sorted_datasets]
    
    # 统计真实的热门模型
    model_counts = db.query(
        VLMTask.model_id, 
        func.count(VLMTask.id).label('usage_count')
    ).group_by(VLMTask.model_id).order_by(func.count(VLMTask.id).desc()).limit(3).all()
    
    popular_models = [
        {"name": model_id, "usage_count": count} 
        for model_id, count in model_counts
    ]
    
    return {
        "total_tasks": total_tasks,
        "running_tasks": running_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "average_duration_minutes": avg_duration_minutes,
        "popular_datasets": popular_datasets,
        "popular_models": popular_models
    }


