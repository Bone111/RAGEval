from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_current_user, get_db
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
    current_user: User = Depends(get_optional_current_user)
):
    """
    获取用户所有模型配置（支持可选认证）
    - 已认证：返回用户的个人配置
    - 未认证：返回第一个用户的配置（开发模式）
    """
    # 如果未认证，使用第一个用户（开发模式）
    if not current_user:
        print("DEBUG - 未认证用户请求模型配置，使用第一个用户（开发模式）")
        from sqlalchemy import text
        user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
        if not user_result:
            print("DEBUG - 数据库中无用户，返回空列表")
            return []
        user_id = str(user_result.id)
        print(f"DEBUG - 使用用户ID: {user_id}")
    else:
        user_id = current_user.id
        print(f"DEBUG - 用户 {current_user.name} 请求模型配置")
    
    configs = db.query(UserModelConfig).filter(
        UserModelConfig.user_id == user_id,
        UserModelConfig.is_active == True
    ).order_by(UserModelConfig.created_at.desc()).all()
    print(f"DEBUG - 找到 {len(configs)} 个模型配置")
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
    current_user: User = Depends(get_optional_current_user)
):
    """
    获取用户所有RAG配置（支持可选认证）
    - 已认证：返回用户的个人配置
    - 未认证：返回第一个用户的配置（开发模式）
    """
    # 如果未认证，使用第一个用户（开发模式）
    if not current_user:
        print("DEBUG - 未认证用户请求RAG配置，使用第一个用户（开发模式）")
        from sqlalchemy import text
        user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
        if not user_result:
            print("DEBUG - 数据库中无用户，返回空列表")
            return []
        user_id = str(user_result.id)
        print(f"DEBUG - 使用用户ID: {user_id}")
    else:
        user_id = current_user.id
        print(f"DEBUG - 用户 {current_user.name} 请求RAG配置")
    
    configs = db.query(UserRAGConfig).filter(
        UserRAGConfig.user_id == user_id,
        UserRAGConfig.is_active == True
    ).order_by(UserRAGConfig.created_at.desc()).all()
    print(f"DEBUG - 找到 {len(configs)} 个RAG配置")
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


# ==================== 模型连接测试（后端代理）====================

@router.post("/model-configs/test-connection")
async def test_model_connection(
    config_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_current_user)
):
    """测试模型API连接（后端代理，避免CORS问题）"""
    import requests
    import json as json_lib
    
    print(f"📥 收到测试连接请求")
    
    try:
        base_url = config_data.get('baseUrl') or config_data.get('base_url')
        api_key = config_data.get('apiKey') or config_data.get('api_key')
        model_name = config_data.get('modelName') or config_data.get('model_name')
        additional_params = config_data.get('additionalParams') or config_data.get('additional_params') or {}
        
        print(f"📋 参数: base_url={base_url}, model={model_name}")
        
        if not base_url:
            raise HTTPException(status_code=400, detail="缺少 base_url 参数")
        if not api_key:
            raise HTTPException(status_code=400, detail="缺少 api_key 参数")
        if not model_name:
            raise HTTPException(status_code=400, detail="缺少 model_name 参数")
        
        # 解析 additional_params
        if isinstance(additional_params, str):
            try:
                additional_params = json_lib.loads(additional_params)
            except:
                additional_params = {}
        
        # 构建请求
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "RAGEval/1.0"
        }
        
        # 确保 base_url 格式正确
        if not base_url.endswith('/'):
            base_url += '/'
        
        # 构建完整URL
        chat_url = f"{base_url}chat/completions"
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": "你好"}
            ],
            "max_tokens": 10,
            **additional_params
        }
        
        print(f"🔗 测试连接: {chat_url}")
        
        # 使用requests库（更稳定，兼容性更好）
        import warnings
        warnings.filterwarnings('ignore', message='Unverified HTTPS request')
        
        response = requests.post(
            chat_url,
            headers=headers,
            json=payload,
            timeout=30,
            verify=False  # 跳过SSL验证
        )
        
        print(f"📡 响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"✅ 连接成功: {content[:30]}")
            return {
                "success": True,
                "message": "连接成功！",
                "response": content[:50] if content else "模型返回为空",
                "status_code": 200
            }
        else:
            error_text = response.text
            print(f"❌ API错误: {response.status_code} - {error_text[:200]}")
            return {
                "success": False,
                "message": f"API返回错误: {response.status_code}",
                "error": error_text[:200],
                "status_code": response.status_code
            }
                
    except requests.exceptions.Timeout:
        print("⏱️  连接超时")
        raise HTTPException(status_code=408, detail="连接超时，请检查网络或API地址")
    except requests.exceptions.ConnectionError as e:
        print(f"🔌 连接失败: {str(e)}")
        raise HTTPException(status_code=503, detail=f"无法连接到API，请检查网络连接或API地址")
    except Exception as e:
        print(f"❌ 测试连接失败: {str(e)}")
        print(f"❌ 错误类型: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")
