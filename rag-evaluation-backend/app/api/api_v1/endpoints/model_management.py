"""
大模型统一管理API接口
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.services.model_management_service import ModelManagementService
from app.models.user import User
from typing import Optional

router = APIRouter()


# ==================== Pydantic 模型 ====================

class ModelOverviewResponse(BaseModel):
    """模型总览响应"""
    total_models: int
    type_distribution: Dict[str, int]
    status_distribution: Dict[str, int]
    recent_used: List[Dict[str, Any]]
    favorites: List[Dict[str, Any]]
    total_disk_usage: int
    downloading_tasks: int


class ModelListResponse(BaseModel):
    """模型列表响应"""
    total: int
    page: int
    page_size: int
    models: List[Dict[str, Any]]


class ModelDetailResponse(BaseModel):
    """模型详情响应"""
    id: int
    model_id: str
    model_name: str
    display_name: Optional[str]
    model_type: str
    status: str
    usage_stats: Dict[str, Any]
    categories: List[Dict[str, Any]]


class ModelUpdateRequest(BaseModel):
    """模型更新请求"""
    display_name: Optional[str] = None
    notes: Optional[str] = None
    is_favorite: Optional[bool] = None
    tags: Optional[List[str]] = None
    quality_rating: Optional[float] = Field(None, ge=1, le=10)
    capabilities: Optional[List[str]] = None
    languages: Optional[List[str]] = None


class LocalScanRequest(BaseModel):
    """本地扫描请求"""
    scan_paths: List[str]


class LocalScanResponse(BaseModel):
    """本地扫描响应"""
    scanned_paths: List[str]
    found_models: List[Dict[str, Any]]
    errors: List[str]


class ModelRegistrationRequest(BaseModel):
    """模型注册请求"""
    registry_id: int
    display_name: Optional[str] = None
    notes: Optional[str] = None


class LocalModelToggleRequest(BaseModel):
    """本地模型开关切换请求"""
    registry_id: int
    is_enabled: bool


class BatchLocalModelToggleRequest(BaseModel):
    """批量本地模型开关切换请求"""
    registry_ids: List[int]
    is_enabled: bool


class UsageLogRequest(BaseModel):
    """使用日志请求"""
    usage_type: str = Field(..., description="使用类型：chat, eval, generation等")
    task_name: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    throughput: Optional[float] = None
    cost_estimate: Optional[float] = None
    quality_score: Optional[float] = Field(None, ge=1, le=10)
    user_rating: Optional[int] = Field(None, ge=1, le=5)
    extra_data: Optional[Dict[str, Any]] = None


class CopyModelRequest(BaseModel):
    """复制模型请求"""
    source_model_id: int = Field(..., description="源模型ID")
    model_name: str = Field(..., min_length=1, max_length=100, description="新模型名称")
    display_name: str = Field(..., min_length=1, max_length=100, description="新显示名称")
    notes: Optional[str] = Field(None, max_length=500, description="备注信息")


# ==================== API 接口 ====================

@router.get("/test")
async def test_endpoint():
    """测试API是否正常工作（不需要认证）"""
    return {"status": "API正常工作", "timestamp": "2025-10-11"}

@router.get("/overview-test")
async def get_models_overview_test(db: Session = Depends(get_db)):
    """获取模型总览统计（临时测试版本，不需要认证）"""
    # 使用第一个找到的用户ID来测试
    from sqlalchemy import text
    user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
    if not user_result:
        return {
            'total_models': 0,
            'type_distribution': {},
            'status_distribution': {},
            'recent_used': [],
            'favorites': [],
            'total_disk_usage': 0,
            'downloading_tasks': 0
        }
    
    service = ModelManagementService(db)
    try:
        overview = await service.get_models_overview(str(user_result.id))
        return overview
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型总览失败: {str(e)}")

@router.get("/overview", response_model=ModelOverviewResponse)
async def get_models_overview(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取模型总览统计"""
    service = ModelManagementService(db)
    try:
        overview = await service.get_models_overview(str(current_user.id))
        return overview
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型总览失败: {str(e)}")


@router.get("/list-test")
async def get_models_list_test(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取模型列表（临时测试版本）- 优先使用有配置的用户"""
    from sqlalchemy import text
    
    # 优先查找有模型配置的用户（修复PostgreSQL DISTINCT + ORDER BY问题）
    user_result = db.execute(text("""
        SELECT u.id, u.created_at
        FROM users u
        WHERE EXISTS (
            SELECT 1 FROM user_model_configs umc 
            WHERE umc.user_id = u.id AND umc.is_active = true
        )
        ORDER BY u.created_at DESC
        LIMIT 1
    """)).first()
    
    # 如果没有有配置的用户，使用第一个用户
    if not user_result:
        user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
    
    if not user_result:
        return {'total': 0, 'models': []}
    
    service = ModelManagementService(db)
    try:
        result = await service.get_models_list(
            user_id=str(user_result.id),
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")

@router.get("/list", response_model=ModelListResponse)
async def get_models_list(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    model_type: Optional[str] = Query(None, description="模型类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    sort_by: str = Query("created_at", description="排序字段"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="排序方向"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取模型列表"""
    service = ModelManagementService(db)
    try:
        result = await service.get_models_list(
            user_id=str(current_user.id),
            page=page,
            page_size=page_size,
            model_type=model_type,
            status=status,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")


@router.get("/{model_id}/detail-test")
async def get_model_detail_test(
    model_id: int,
    db: Session = Depends(get_db)
):
    """获取模型详细信息（测试版本）- 智能查找模型所属用户"""
    from sqlalchemy import text
    
    # 先查找该模型所属的用户
    model_user = db.execute(text(f"""
        SELECT user_id FROM model_info WHERE id = {model_id}
    """)).first()
    
    if not model_user:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    service = ModelManagementService(db)
    try:
        model_detail = await service.get_model_detail(str(model_user.user_id), model_id)
        if not model_detail:
            raise HTTPException(status_code=404, detail="模型不存在")
        return model_detail
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型详情失败: {str(e)}")

@router.get("/{model_id}")
async def get_model_detail(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取模型详细信息"""
    service = ModelManagementService(db)
    try:
        model_detail = await service.get_model_detail(str(current_user.id), model_id)
        if not model_detail:
            raise HTTPException(status_code=404, detail="模型不存在")
        return model_detail
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型详情失败: {str(e)}")


@router.put("/{model_id}")
async def update_model(
    model_id: int,
    updates: ModelUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新模型信息"""
    service = ModelManagementService(db)
    try:
        success = await service.update_model_info(
            user_id=str(current_user.id),
            model_id=model_id,
            updates=updates.dict(exclude_unset=True)
        )
        if not success:
            raise HTTPException(status_code=404, detail="模型不存在或更新失败")
        return {"success": True, "message": "模型信息更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新模型失败: {str(e)}")


@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除模型"""
    service = ModelManagementService(db)
    try:
        success = await service.delete_model(str(current_user.id), model_id)
        if not success:
            raise HTTPException(status_code=404, detail="模型不存在或删除失败")
        return {"success": True, "message": "模型删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除模型失败: {str(e)}")


@router.post("/scan-local", response_model=LocalScanResponse)
async def scan_local_models(
    request: LocalScanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """扫描本地模型"""
    service = ModelManagementService(db)
    try:
        result = await service.scan_local_models(request.scan_paths)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描本地模型失败: {str(e)}")


@router.get("/local-registry/list-test")
async def get_local_registry_test(db: Session = Depends(get_db)):
    """获取本地模型注册表（测试版本）"""
    service = ModelManagementService(db)
    try:
        registry_entries = await service.get_local_registry_entries()
        return {"registry_entries": registry_entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取本地模型注册表失败: {str(e)}")

@router.get("/local-registry/list")
async def get_local_registry(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取本地模型注册表"""
    service = ModelManagementService(db)
    try:
        registry_entries = await service.get_local_registry_entries()
        return {"registry_entries": registry_entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取本地模型注册表失败: {str(e)}")


@router.post("/register-local")
async def register_local_model(
    request: ModelRegistrationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """注册本地模型"""
    service = ModelManagementService(db)
    try:
        custom_info = {}
        if request.display_name:
            custom_info['display_name'] = request.display_name
        if request.notes:
            custom_info['notes'] = request.notes
        
        model_id = await service.register_local_model(
            user_id=str(current_user.id),
            registry_id=request.registry_id,
            custom_info=custom_info if custom_info else None
        )
        
        if not model_id:
            raise HTTPException(status_code=404, detail="本地模型注册失败")
        
        return {"success": True, "model_id": model_id, "message": "本地模型注册成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"注册本地模型失败: {str(e)}")


@router.post("/{model_id}/usage-log")
async def log_model_usage(
    model_id: int,
    usage_log: UsageLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """记录模型使用日志"""
    service = ModelManagementService(db)
    try:
        success = await service.log_model_usage(
            user_id=str(current_user.id),
            model_id=model_id,
            usage_type=usage_log.usage_type,
            usage_data=usage_log.dict(exclude_unset=True)
        )
        if not success:
            raise HTTPException(status_code=400, detail="记录使用日志失败")
        return {"success": True, "message": "使用日志记录成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"记录使用日志失败: {str(e)}")


@router.get("/categories/list")
async def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取模型分类列表"""
    service = ModelManagementService(db)
    try:
        categories = await service.get_categories()
        return {"categories": categories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取分类列表失败: {str(e)}")


@router.post("/{model_id}/category/{category_id}")
async def add_model_to_category(
    model_id: int,
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """将模型添加到分类"""
    service = ModelManagementService(db)
    try:
        success = await service.add_model_to_category(model_id, category_id)
        if not success:
            raise HTTPException(status_code=400, detail="添加分类失败")
        return {"success": True, "message": "分类添加成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加分类失败: {str(e)}")


@router.post("/auto-register-local-test")
async def auto_register_local_models_test(db: Session = Depends(get_db)):
    """自动注册所有发现的本地模型（测试版本）"""
    from sqlalchemy import text
    user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
    if not user_result:
        return {"success": False, "message": "没有找到用户"}
    
    service = ModelManagementService(db)
    try:
        registered_count = await service.auto_register_discovered_models(str(user_result.id))
        return {
            "success": True,
            "message": f"成功注册 {registered_count} 个本地模型",
            "registered_count": registered_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自动注册本地模型失败: {str(e)}")


@router.post("/local-registry/toggle-test")
async def toggle_local_model_test(
    request: LocalModelToggleRequest,
    db: Session = Depends(get_db)
):
    """切换本地模型的启用/禁用状态（测试版本）"""
    from sqlalchemy import text
    user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
    if not user_result:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    service = ModelManagementService(db)
    try:
        success = await service.toggle_local_model_enabled(
            request.registry_id, 
            request.is_enabled, 
            str(user_result.id)
        )
        if not success:
            raise HTTPException(status_code=404, detail="切换状态失败")
        
        action = "启用" if request.is_enabled else "禁用"
        return {"success": True, "message": f"成功{action}模型"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换模型状态失败: {str(e)}")


@router.post("/local-registry/toggle")
async def toggle_local_model(
    request: LocalModelToggleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """切换本地模型的启用/禁用状态"""
    service = ModelManagementService(db)
    try:
        success = await service.toggle_local_model_enabled(
            request.registry_id, 
            request.is_enabled, 
            str(current_user.id)
        )
        if not success:
            raise HTTPException(status_code=404, detail="切换状态失败")
        
        action = "启用" if request.is_enabled else "禁用"
        return {"success": True, "message": f"成功{action}模型"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"切换模型状态失败: {str(e)}")


# ==================== 统计接口 ====================

@router.get("/stats/usage")
async def get_usage_statistics(
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    current_user: User = Depends(get_current_user)
):
    """获取使用统计"""
    # 这里可以添加详细的使用统计逻辑
    return {
        "total_usage": 0,
        "daily_usage": {},
        "usage_by_model": {},
        "usage_by_type": {}
    }


@router.get("/stats/performance")
async def get_performance_statistics(
    current_user: User = Depends(get_current_user)
):
    """获取性能统计"""
    # 这里可以添加性能统计逻辑
    return {
        "avg_latency": 0,
        "avg_throughput": 0,
        "performance_trends": {}
    }


@router.post("/sync-existing-test")
async def sync_existing_models_test(db: Session = Depends(get_db)):
    """同步现有的模型配置到统一管理系统（临时测试版本）- 优先使用有配置的用户"""
    from sqlalchemy import text
    
    # 优先查找有模型配置的用户
    user_result = db.execute(text("""
        SELECT u.id, u.created_at
        FROM users u
        WHERE EXISTS (
            SELECT 1 FROM user_model_configs umc 
            WHERE umc.user_id = u.id AND umc.is_active = true
        )
        ORDER BY u.created_at DESC
        LIMIT 1
    """)).first()
    
    # 如果没有有配置的用户，使用第一个用户
    if not user_result:
        user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
    
    if not user_result:
        return {"success": False, "message": "没有找到用户"}
    
    service = ModelManagementService(db)
    try:
        result = await service.sync_existing_models(str(user_result.id))
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        # 构建详细消息
        msg_parts = []
        if result.get('removed_models', 0) > 0:
            msg_parts.append(f"清理: {result['removed_models']}个")
        msg_parts.append(f"用户配置: {result['synced_user_configs']}个")
        msg_parts.append(f"传统配置: {result['synced_model_configs']}个")
        msg_parts.append(f"发现本地模型: {result['scanned_local_models']}个")
        msg_parts.append(f"注册本地模型: {result.get('auto_registered_models', 0)}个")
        
        return {
            "success": True,
            "message": f"同步完成！{', '.join(msg_parts)}",
            "details": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步现有模型失败: {str(e)}")


@router.post("/{model_id}/increment-usage-test")
async def increment_usage_test(
    model_id: int,
    db: Session = Depends(get_db)
):
    """手动增加模型使用统计（测试用途）"""
    service = ModelManagementService(db)
    try:
        # 直接通过数据库ID查找模型并更新统计
        from app.models.model_management import ModelInfo
        model = db.query(ModelInfo).filter(ModelInfo.id == model_id).first()
        
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")
        
        # 手动增加使用统计
        success = service.log_model_usage_by_name_sync(
            model_name=model.model_name,
            usage_type='manual_test',
            task_name='手动测试统计更新',
            user_id=model.user_id
        )
        
        if success:
            # 重新获取更新后的模型数据
            db.refresh(model)
            return {
                "success": True, 
                "message": f"模型 {model.model_name} 使用统计已更新",
                "new_usage_count": model.usage_count,
                "model_name": model.model_name,
                "last_used_at": model.last_used_at.isoformat() if model.last_used_at else None
            }
        else:
            raise HTTPException(status_code=500, detail="更新使用统计失败")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"增加使用统计失败: {str(e)}")


@router.post("/sync-existing")
async def sync_existing_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """同步现有的模型配置到统一管理系统"""
    service = ModelManagementService(db)
    try:
        result = await service.sync_existing_models(str(current_user.id))
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        return {
            "success": True,
            "message": f"同步完成！用户配置: {result['synced_user_configs']}个，传统配置: {result['synced_model_configs']}个，本地模型: {result['scanned_local_models']}个",
            "details": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步现有模型失败: {str(e)}")


@router.post("/refresh-model-names")
async def refresh_model_names(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """刷新模型名称，从配置中获取真实名称（token无效时自动使用默认用户）"""
    service = ModelManagementService(db)
    try:
        # 如果token无效，使用第一个用户
        if not current_user:
            from sqlalchemy import text
            user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
            if not user_result:
                raise HTTPException(status_code=500, detail="系统中没有用户，请先创建用户")
            user_id = str(user_result.id)
        else:
            user_id = str(current_user.id)
        
        updated_count = await service.refresh_model_display_names(user_id)
        return {
            "success": True,
            "message": f"已更新 {updated_count} 个模型的显示名称",
            "updated_count": updated_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新模型名称失败: {str(e)}")


@router.post("/copy-model-test")
async def copy_model_test(
    request: CopyModelRequest,
    db: Session = Depends(get_db)
):
    """复制模型（测试版本）"""
    from sqlalchemy import text
    user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
    if not user_result:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    service = ModelManagementService(db)
    try:
        new_model_id = await service.copy_model(
            user_id=str(user_result.id),
            source_model_id=request.source_model_id,
            new_model_name=request.model_name,
            new_display_name=request.display_name,
            notes=request.notes
        )
        
        if not new_model_id:
            raise HTTPException(status_code=400, detail="复制模型失败")
        
        return {
            "success": True,
            "message": f"成功复制模型，新模型ID: {new_model_id}",
            "new_model_id": new_model_id
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"复制模型失败: {str(e)}")


@router.post("/copy-model")
async def copy_model(
    request: CopyModelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """复制模型"""
    service = ModelManagementService(db)
    try:
        new_model_id = await service.copy_model(
            user_id=str(current_user.id),
            source_model_id=request.source_model_id,
            new_model_name=request.model_name,
            new_display_name=request.display_name,
            notes=request.notes
        )
        
        if not new_model_id:
            raise HTTPException(status_code=400, detail="复制模型失败")
        
        return {
            "success": True,
            "message": f"成功复制模型，新模型ID: {new_model_id}",
            "new_model_id": new_model_id
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"复制模型失败: {str(e)}")
