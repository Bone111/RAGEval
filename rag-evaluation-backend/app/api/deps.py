from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=not settings.DISABLE_AUTH))
) -> User:
    # 🔥 新增：如果禁用认证，返回默认用户
    if settings.DISABLE_AUTH:
        print("DEBUG - 认证已禁用，返回默认用户")
        # 返回第一个找到的用户作为默认用户
        from sqlalchemy import text
        user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
        if user_result:
            return db.query(User).filter(User.id == user_result.id).first()
        raise HTTPException(status_code=404, detail="没有找到用户")
    
    print(f"DEBUG - 获取当前用户: 令牌前15个字符 {token[:15]}...")
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        print(f"DEBUG - JWT解码成功: {payload}")
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        print("DEBUG - JWT解码失败")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证凭据无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == token_data.sub).first()

    if not user:
        raise HTTPException(status_code=404, detail="用户未找到")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户未激活")
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    获取当前活跃用户（已登录且未停用）
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="用户已停用")
    return current_user

def get_current_active_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    获取当前管理员用户
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, 
            detail="权限不足"
        )
    return current_user

# # 创建一个假测试用户对象
# test_user = User(
#     id=uuid.uuid4(),
#     email="test@example.com",
#     name="测试用户",
#     is_active=True,
#     is_admin=True  # 赋予管理员权限以访问所有内容
# )
#
# def get_test_user():
#     """
#     开发/测试环境使用的模拟用户依赖项，
#     总是返回一个有效的测试用户，不需要验证
#     """
#     return test_user
#     return test_user

def get_optional_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False))
) -> Optional[User]:
    """
    获取当前用户（可选）
    如果没有提供token或token无效，返回None而不是抛出异常
    这允许接口支持公开访问和认证访问两种模式
    """
    # 🔥 新增：如果禁用认证，返回默认用户
    if settings.DISABLE_AUTH:
        print("DEBUG - 认证已禁用，返回默认用户")
        # 返回第一个找到的用户作为默认用户
        from sqlalchemy import text
        user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
        if user_result:
            return db.query(User).filter(User.id == user_result.id).first()
        return None
    
    if not token:
        print("DEBUG - 未提供认证令牌，返回None")
        return None
    
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[ALGORITHM]
        )
        print(f"DEBUG - JWT解码成功: {payload}")
        token_data = TokenPayload(**payload)
        
        user = db.query(User).filter(User.id == token_data.sub).first()
        
        if not user or not user.is_active:
            print("DEBUG - 用户不存在或未激活，返回None")
            return None
            
        print(f"DEBUG - 认证成功，用户: {user.name}")
        return user
        
    except (JWTError, ValidationError) as e:
        print(f"DEBUG - JWT解码失败: {e}，返回None")
        return None

def get_current_user_flexible(
    db: Session = Depends(get_db),
    token: str = Depends(OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False))
) -> User:
    """
    🔥 新增：灵活的用户认证依赖
    - 如果启用认证且提供有效token，返回认证用户
    - 如果禁用认证，返回默认用户
    - 如果启用认证但token无效，抛出401异常
    """
    if settings.DISABLE_AUTH:
        print("DEBUG - 认证已禁用，返回默认用户")
        # 返回第一个找到的用户作为默认用户
        from sqlalchemy import text
        user_result = db.execute(text("SELECT id FROM users LIMIT 1")).first()
        if user_result:
            default_user = db.query(User).filter(User.id == user_result.id).first()
            if default_user:
                return default_user
        
        raise HTTPException(
            status_code=500,
            detail="认证已禁用但找不到默认用户，请创建用户或启用认证"
        )
    
    # 启用认证模式，使用标准认证流程
    return get_current_user(db, token)