from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.user_config import UserModelConfig, UserRAGConfig
from app.schemas.user_config import (
    UserModelConfigCreate, UserModelConfigUpdate, UserModelConfigOut,
    UserRAGConfigCreate, UserRAGConfigUpdate, UserRAGConfigOut
)

router = APIRouter()

# ==================== 模型配置管理 ====================

@router.post("/model-configs", response_model=UserModelConfigOut)
def create_model_config(
    config_in: UserModelConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建用户模型配置"""
    # 检查同名配置是否已存在
    existing = db.query(UserModelConfig).filter(
        UserModelConfig.user_id == current_user.id,
        UserModelConfig.name == config_in.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="配置名称已存在")
    
    db_obj = UserModelConfig(**config_in.model_dump(), user_id=current_user.id)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


@router.get("/model-configs", response_model=List[UserModelConfigOut])
def get_model_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户所有模型配置"""
    configs = db.query(UserModelConfig).filter(
        UserModelConfig.user_id == current_user.id
    ).order_by(UserModelConfig.created_at.desc()).all()
    return configs


@router.get("/model-configs/{config_id}", response_model=UserModelConfigOut)
def get_model_config(
    config_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定模型配置"""
    config = db.query(UserModelConfig).filter(
        UserModelConfig.id == config_id,
        UserModelConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    return config


@router.put("/model-configs/{config_id}", response_model=UserModelConfigOut)
def update_model_config(
    config_id: str,
    config_in: UserModelConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新模型配置"""
    config = db.query(UserModelConfig).filter(
        UserModelConfig.id == config_id,
        UserModelConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    # 检查是否与其他配置重名
    if config_in.name and config_in.name != config.name:
        existing = db.query(UserModelConfig).filter(
            UserModelConfig.user_id == current_user.id,
            UserModelConfig.name == config_in.name,
            UserModelConfig.id != config_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="配置名称已存在")
    
    update_data = config_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    return config


@router.delete("/model-configs/{config_id}")
def delete_model_config(
    config_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除模型配置"""
    config = db.query(UserModelConfig).filter(
        UserModelConfig.id == config_id,
        UserModelConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    db.delete(config)
    db.commit()
    return {"message": "配置删除成功"}


# ==================== RAG配置管理 ====================

@router.post("/rag-configs", response_model=UserRAGConfigOut)
def create_rag_config(
    config_in: UserRAGConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建用户RAG配置"""
    # 检查同名配置是否已存在
    existing = db.query(UserRAGConfig).filter(
        UserRAGConfig.user_id == current_user.id,
        UserRAGConfig.name == config_in.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="配置名称已存在")
    
    db_obj = UserRAGConfig(**config_in.model_dump(), user_id=current_user.id)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


@router.get("/rag-configs", response_model=List[UserRAGConfigOut])
def get_rag_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户所有RAG配置"""
    configs = db.query(UserRAGConfig).filter(
        UserRAGConfig.user_id == current_user.id
    ).order_by(UserRAGConfig.created_at.desc()).all()
    return configs


@router.get("/rag-configs/{config_id}", response_model=UserRAGConfigOut)
def get_rag_config(
    config_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取指定RAG配置"""
    config = db.query(UserRAGConfig).filter(
        UserRAGConfig.id == config_id,
        UserRAGConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    return config


@router.put("/rag-configs/{config_id}", response_model=UserRAGConfigOut)
def update_rag_config(
    config_id: str,
    config_in: UserRAGConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新RAG配置"""
    config = db.query(UserRAGConfig).filter(
        UserRAGConfig.id == config_id,
        UserRAGConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    # 检查是否与其他配置重名
    if config_in.name and config_in.name != config.name:
        existing = db.query(UserRAGConfig).filter(
            UserRAGConfig.user_id == current_user.id,
            UserRAGConfig.name == config_in.name,
            UserRAGConfig.id != config_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="配置名称已存在")
    
    update_data = config_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    return config


@router.delete("/rag-configs/{config_id}")
def delete_rag_config(
    config_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除RAG配置"""
    config = db.query(UserRAGConfig).filter(
        UserRAGConfig.id == config_id,
        UserRAGConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    
    db.delete(config)
    db.commit()
    return {"message": "配置删除成功"}


# ==================== 通用配置管理 ====================

@router.get("/configs/search")
def search_configs(
    name: str = None,
    type: str = None,
    config_type: str = None,  # 'model' or 'rag'
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """搜索配置（支持按名称和类型搜索）"""
    result = {"model_configs": [], "rag_configs": []}
    
    if not config_type or config_type == "model":
        model_query = db.query(UserModelConfig).filter(
            UserModelConfig.user_id == current_user.id
        )
        
        if name:
            model_query = model_query.filter(UserModelConfig.name.ilike(f"%{name}%"))
        if type:
            model_query = model_query.filter(UserModelConfig.type == type)
            
        result["model_configs"] = model_query.all()
    
    if not config_type or config_type == "rag":
        rag_query = db.query(UserRAGConfig).filter(
            UserRAGConfig.user_id == current_user.id
        )
        
        if name:
            rag_query = rag_query.filter(UserRAGConfig.name.ilike(f"%{name}%"))
        if type:
            rag_query = rag_query.filter(UserRAGConfig.type == type)
            
        result["rag_configs"] = rag_query.all()
    
    return result


@router.delete("/configs/clear-all")
def clear_all_configs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清除用户所有配置"""
    # 删除所有模型配置
    model_configs = db.query(UserModelConfig).filter(
        UserModelConfig.user_id == current_user.id
    ).all()
    model_count = len(model_configs)
    
    for config in model_configs:
        db.delete(config)
    
    # 删除所有RAG配置
    rag_configs = db.query(UserRAGConfig).filter(
        UserRAGConfig.user_id == current_user.id
    ).all()
    rag_count = len(rag_configs)
    
    for config in rag_configs:
        db.delete(config)
    
    db.commit()
    
    return {
        "message": "所有配置已清除",
        "deleted_model_configs": model_count,
        "deleted_rag_configs": rag_count
    }
