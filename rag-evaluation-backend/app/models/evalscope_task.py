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
    # 添加时间追踪字段
    first_started_at = Column(DateTime(timezone=True), nullable=True)  # 首次开始时间
    total_paused_duration = Column(Integer, default=0)  # 总暂停时长（秒）
    work_dir = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    extra_metadata = Column(JSON, default={})

    # 关系
    results = relationship("EvalScopeResult", back_populates="task", cascade="all, delete-orphan")
    
    def get_effective_duration(self) -> int:
        """计算有效执行时长（总时间 - 暂停时间）"""
        if not self.first_started_at or not self.completed_at:
            return 0
        
        # 处理时区问题：确保两个时间都是aware或都是naive
        completed_at = self.completed_at
        first_started_at = self.first_started_at
        
        # 如果一个是aware，另一个是naive，将naive的转换为aware
        if completed_at.tzinfo is not None and first_started_at.tzinfo is None:
            # completed_at是aware，first_started_at是naive
            first_started_at = first_started_at.replace(tzinfo=completed_at.tzinfo)
        elif completed_at.tzinfo is None and first_started_at.tzinfo is not None:
            # first_started_at是aware，completed_at是naive
            completed_at = completed_at.replace(tzinfo=first_started_at.tzinfo)
        
        total_duration = int((completed_at - first_started_at).total_seconds())
        return max(0, total_duration - self.total_paused_duration)
    
    def add_pause_duration(self, pause_seconds: int):
        """添加暂停时长"""
        self.total_paused_duration += pause_seconds


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

