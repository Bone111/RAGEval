from typing import Any, List, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import get_current_active_admin, get_db
from app.models.user import User
from app.models.project import Project
from app.models.dataset import Dataset
from app.models.question import Question
from app.schemas.dataset import DatasetOut
from app.schemas.project import ProjectOut
from app.schemas.user import UserOut, AdminResetPasswordRequest
from app.core.security import get_password_hash

router = APIRouter()

@router.get("/statistics", response_model=Dict[str, Any])
def get_system_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    """
    获取系统统计信息（仅管理员可访问）
    """
    # 用户统计
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()
    admin_users = db.query(func.count(User.id)).filter(User.is_admin == True).scalar()
    
    # 项目统计
    total_projects = db.query(func.count(Project.id)).scalar()
    
    # 数据集统计
    total_datasets = db.query(func.count(Dataset.id)).scalar()
    public_datasets = db.query(func.count(Dataset.id)).filter(Dataset.is_public == True).scalar()
    
    # 问题统计
    total_questions = db.query(func.count(Question.id)).scalar()
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "admin": admin_users
        },
        "projects": {
            "total": total_projects
        },
        "datasets": {
            "total": total_datasets,
            "public": public_datasets
        },
        "questions": {
            "total": total_questions
        }
    }

@router.get("/users", response_model=List[UserOut])
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
) -> Any:
    """
    获取所有用户列表（仅管理员可访问）
    """
    users = db.query(User).all()
    return users

@router.post("/reset-password")
def admin_reset_user_password(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_admin),
    request: AdminResetPasswordRequest,
) -> Any:
    """
    管理员重置用户密码
    """
    # 查找目标用户
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新密码
    user.password_hash = get_password_hash(request.new_password)
    # 清除重置令牌（如果存在）
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    
    return {"message": f"用户 {user.email} 的密码已重置成功"}
