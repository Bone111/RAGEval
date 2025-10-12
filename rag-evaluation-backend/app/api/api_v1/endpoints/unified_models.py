"""
统一模型API接口 - 为所有评测功能提供模型服务
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user, get_db
from app.services.unified_model_service import UnifiedModelService
from app.models.user import User

router = APIRouter()


class ModelResponse(BaseModel):
    """模型响应"""
    id: str
    name: str
    display_name: str
    model_type: str
    model_family: Optional[str]
    model_size: Optional[str]
    capabilities: List[str]
    languages: List[str]
    tags: List[str]
    status: str
    usage_count: int
    quality_rating: Optional[float]
    is_favorite: bool
    config: Dict[str, Any]


class ModelsListResponse(BaseModel):
    """模型列表响应"""
    models: List[ModelResponse]
    total: int


@router.get("/available", response_model=ModelsListResponse)
async def get_available_models(
    model_types: Optional[str] = Query(None, description="模型类型过滤，逗号分隔"),
    capabilities: Optional[str] = Query(None, description="能力过滤，逗号分隔"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户可用的模型列表"""
    service = UnifiedModelService(db)
    try:
        # 解析过滤参数
        model_types_list = model_types.split(',') if model_types else None
        capabilities_list = capabilities.split(',') if capabilities else None
        
        models = await service.get_available_models(
            user_id=str(current_user.id),
            model_types=model_types_list,
            capabilities=capabilities_list
        )
        
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取可用模型失败: {str(e)}")


@router.get("/chat", response_model=ModelsListResponse)
async def get_chat_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取支持对话的模型"""
    service = UnifiedModelService(db)
    try:
        models = await service.get_chat_models(str(current_user.id))
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对话模型失败: {str(e)}")


@router.get("/code", response_model=ModelsListResponse)
async def get_code_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取支持代码生成的模型"""
    service = UnifiedModelService(db)
    try:
        models = await service.get_code_models(str(current_user.id))
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取代码模型失败: {str(e)}")


@router.get("/multimodal", response_model=ModelsListResponse)
async def get_multimodal_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取多模态模型"""
    service = UnifiedModelService(db)
    try:
        models = await service.get_multimodal_models(str(current_user.id))
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取多模态模型失败: {str(e)}")


@router.get("/local", response_model=ModelsListResponse)
async def get_local_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取本地模型"""
    service = UnifiedModelService(db)
    try:
        models = await service.get_local_models(str(current_user.id))
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取本地模型失败: {str(e)}")


@router.get("/api", response_model=ModelsListResponse)
async def get_api_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取API模型"""
    service = UnifiedModelService(db)
    try:
        models = await service.get_api_models(str(current_user.id))
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取API模型失败: {str(e)}")


@router.get("/comparison", response_model=ModelsListResponse)
async def get_models_for_comparison(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取适合对比的模型"""
    service = UnifiedModelService(db)
    try:
        models = await service.get_models_for_comparison(str(current_user.id))
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取对比模型失败: {str(e)}")


@router.get("/arena", response_model=ModelsListResponse)
async def get_arena_models(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取Arena对战模型"""
    service = UnifiedModelService(db)
    try:
        models = await service.get_arena_models(str(current_user.id))
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Arena模型失败: {str(e)}")


@router.get("/all", response_model=ModelsListResponse)
async def get_all_models(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    获取所有可用模型（包括新版和旧版配置）
    支持可选认证：
    - 如果提供了有效token，返回用户个性化的模型列表
    - 如果未提供token或token无效，返回公共可用的模型列表
    """
    service = UnifiedModelService(db)
    try:
        if current_user:
            # 已认证用户：返回用户个性化的模型列表
            print(f"DEBUG - 已认证用户 {current_user.name} 请求模型列表")
            models = await service.get_all_available_models(str(current_user.id))
        else:
            # 未认证用户：返回公共可用的模型列表
            print("DEBUG - 未认证用户请求模型列表，返回公共模型")
            models = await service.get_public_models()
        
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
    except Exception as e:
        print(f"ERROR - 获取模型列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取所有模型失败: {str(e)}")


@router.get("/{model_id}")
async def get_model_by_id(
    model_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """根据模型ID获取模型信息"""
    service = UnifiedModelService(db)
    try:
        model = await service.get_model_by_id(str(current_user.id), model_id)
        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")
        return model
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型信息失败: {str(e)}")


@router.post("/{model_id}/usage")
async def record_model_usage(
    model_id: str,
    usage_type: str = "eval",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """记录模型使用"""
    service = UnifiedModelService(db)
    try:
        success = await service.record_model_usage(
            user_id=str(current_user.id),
            model_id=model_id,
            usage_type=usage_type
        )
        if not success:
            raise HTTPException(status_code=404, detail="模型不存在")
        return {"success": True, "message": "使用记录成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"记录使用失败: {str(e)}")


# ==================== 兼容性接口 ====================

@router.get("/legacy/user-configs")
async def get_legacy_user_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取旧版用户配置的模型（兼容性接口）"""
    service = UnifiedModelService(db)
    try:
        models = await service.get_legacy_models(str(current_user.id))
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取旧版配置失败: {str(e)}")


# ==================== 测试接口 ====================

@router.get("/test/available")
async def get_available_models_test(
    db: Session = Depends(get_db)
):
    """测试接口 - 获取可用模型（无需认证）"""
    try:
        # 先检查数据库中是否有模型数据
        from app.models.model_management import ModelInfo
        
        # 查询所有用户的模型
        all_models = db.query(ModelInfo).filter(
            ModelInfo.is_active == True
        ).limit(10).all()
        
        print(f"数据库中找到 {len(all_models)} 个模型")
        
        if all_models:
            service = UnifiedModelService(db)
            models = []
            for model in all_models:
                serialized = service._serialize_model_for_eval(model)
                models.append(serialized)
                print(f"模型: {model.model_name}, 类型: {model.model_type}, 状态: {model.status}")
        else:
            print("数据库中没有找到模型数据，返回空列表")
            # 如果没有模型，返回空列表
            # 提示用户需要在【大模型管理】中配置模型
            models = []
        
        return ModelsListResponse(
            models=models,
            total=len(models)
        )
        
    except Exception as e:
        print(f"测试接口异常: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取测试模型失败: {str(e)}")
