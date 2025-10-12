"""
EvalScope评测任务模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ARRAY, ForeignKey, func
from sqlalchemy import JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid

from app.db.base import Base
from app.models.types import StringUUID


def utc_now():
    """返回带时区信息的UTC时间"""
    return datetime.now(timezone.utc)


class EvalScopeTask(Base):
    """EvalScope评测任务"""
    __tablename__ = "evalscope_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(StringUUID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_name = Column(String(255), nullable=False)
    model_id = Column(String(255), nullable=False)
    model_args = Column(JSON, default={})
    datasets = Column(ARRAY(String), nullable=False)
    dataset_args = Column(JSON, default={})
    generation_config = Column(JSON, default={})
    eval_backend = Column(String(50), default='Native')
    eval_type = Column(String(50), default='llm_ckpt')
    status = Column(String(50), default='pending', index=True)
    progress = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    work_dir = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    extra_metadata = Column(JSON, default={})

    # 关系
    results = relationship("EvalScopeResult", back_populates="task", cascade="all, delete-orphan")


class EvalScopeResult(Base):
    """EvalScope评测结果"""
    __tablename__ = "evalscope_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("evalscope_tasks.id", ondelete="CASCADE"), index=True)
    benchmark = Column(String(100), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float)
    category = Column(String(100))
    subset_name = Column(String(100))
    num_samples = Column(Integer)
    raw_results = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), default=utc_now)

    # 关系
    task = relationship("EvalScopeTask", back_populates="results")

