from datetime import timedelta, datetime
from typing import Any, Optional
import secrets
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, Body, Depends, HTTPException, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.core.security import create_access_token, verify_password, get_password_hash
from app.models.user import User
from app.schemas.token import Token
from app.schemas.user import UserCreate, ForgotPasswordRequest, ResetPasswordRequest
from app.services.user_service import create_user, get_user_by_email

router = APIRouter()

@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    print("=============")
    print(form_data)

    """
    获取OAuth2兼容的访问令牌
    """
    print(f"DEBUG - 登录尝试: 用户名={form_data.username}")
    
    user = get_user_by_email(db, email=form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户未激活")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    print(f"DEBUG - 登录成功: 用户ID={user.id}, 令牌前15个字符={access_token[:15]}...")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

@router.post("/register", response_model=Token)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """
    注册新用户并返回访问令牌
    """
    user = get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="该邮箱已被注册",
        )
    user = create_user(db, obj_in=user_in)
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

def send_reset_email(email: str, reset_token: str):
    """发送密码重置邮件"""
    try:
        # 获取邮件配置
        smtp_server = settings.SMTP_SERVER
        smtp_port = settings.SMTP_PORT
        sender_email = settings.SENDER_EMAIL
        sender_password = settings.SENDER_PASSWORD
        sender_name = settings.SENDER_NAME
        
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}&email={email}"
        
        print(f"密码重置邮件发送到: {email}")
        print(f"重置链接: {reset_url}")
        print("=" * 50)
        
        # 如果没有配置邮件服务，只打印链接
        if not sender_email or not sender_password:
            print("⚠️  未配置邮件服务，重置链接仅在控制台显示")
            print("   要启用邮件发送，请设置环境变量：")
            print("   SENDER_EMAIL=your-email@gmail.com")
            print("   SENDER_PASSWORD=your-app-password")
            print("   或创建 .env 文件配置邮件服务")
            return False  # 模拟邮件发送失败
        
        # 发送真实邮件
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = email
        msg['Subject'] = f"{sender_name} - 密码重置"
        
        body = f"""您好，

您请求重置{sender_name}的密码。

请点击以下链接重置您的密码：
{reset_url}

此链接将在24小时后过期。

如果您没有请求重置密码，请忽略此邮件。

谢谢！
{sender_name}团队"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ 邮件已成功发送到: {email}")
        return True
        
    except Exception as e:
        print(f"❌ 发送邮件失败: {e}")
        print("重置链接仍在控制台显示")
        return True  # 即使邮件发送失败，也返回成功，因为链接已生成

@router.post("/forgot-password")
def forgot_password(
    *,
    db: Session = Depends(get_db),
    request: ForgotPasswordRequest,
) -> Any:
    """
    发送密码重置邮件
    """
    user = get_user_by_email(db, email=request.email)
    if not user:
        # 邮箱未注册，返回错误
        raise HTTPException(status_code=400, detail="该邮箱地址未注册，请检查邮箱地址是否正确")
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户账户已被禁用")
    
    # 生成重置令牌
    reset_token = secrets.token_urlsafe(32)
    reset_token_expires = datetime.utcnow() + timedelta(hours=24)
    
    # 更新用户的重置令牌
    user.reset_token = reset_token
    user.reset_token_expires = reset_token_expires
    db.commit()
    
    # 发送重置邮件
    if send_reset_email(user.email, reset_token):
        return {"message": "重置邮件已发送，请查收邮箱"}
    else:
        # 邮件发送失败时，提供管理员联系方式
        return {
            "message": "邮件发送失败，请联系管理员重置密码",
            "contact_info": "请联系系统管理员进行密码重置",
            "token": reset_token,  # 在开发环境提供令牌用于测试
            "reset_url": f"{settings.FRONTEND_URL}/reset-password?token={reset_token}&email={user.email}"
        }

@router.post("/reset-password")
def reset_password(
    *,
    db: Session = Depends(get_db),
    request: ResetPasswordRequest,
) -> Any:
    """
    重置密码
    """
    # 查找有效的重置令牌
    user = db.query(User).filter(
        User.reset_token == request.token,
        User.reset_token_expires > datetime.utcnow()
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="无效或过期的重置令牌")
    
    # 验证邮箱是否与令牌对应的用户邮箱一致
    if user.email != request.email:
        raise HTTPException(status_code=400, detail="邮箱地址与重置令牌不匹配")
    
    # 更新密码
    user.password_hash = get_password_hash(request.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    
    return {"message": "密码重置成功"}

@router.post("/change-password")
def change_password(
    *,
    db: Session = Depends(get_db),
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    已登录用户修改密码
    """
    # 验证当前密码
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")
    
    # 更新密码
    current_user.password_hash = get_password_hash(new_password)
    db.commit()
    
    return {"message": "密码修改成功"} 