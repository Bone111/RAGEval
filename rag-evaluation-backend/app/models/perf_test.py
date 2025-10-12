"""
性能测试任务模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.base import Base
from app.models.types import StringUUID


class PerfTestTask(Base):
    """性能测试任务"""
    __tablename__ = "perf_test_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(StringUUID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    task_name = Column(String(255), nullable=False)
    api_url = Column(String(500), nullable=False)
    api_key = Column(String(500), nullable=True)
    model_name = Column(String(255), nullable=True)
    test_type = Column(String(50), default='single')
    parallel_configs = Column(ARRAY(Integer), default=[10])
    number_configs = Column(ARRAY(Integer), default=[100])
    duration = Column(Integer, nullable=True)
    stream = Column(Boolean, default=False)
    config = Column(JSONB, default={})
    status = Column(String(50), default='pending', index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    extra_metadata = Column(JSONB, default={})

    # 关系
    results = relationship("PerfTestResult", back_populates="task", cascade="all, delete-orphan")


class PerfTestResult(Base):
    """性能测试结果"""
    __tablename__ = "perf_test_results"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("perf_test_tasks.id", ondelete="CASCADE"), index=True)
    parallel = Column(Integer, nullable=False)
    number = Column(Integer, nullable=False)
    qps = Column(Float)
    avg_latency = Column(Float)
    ttft = Column(Float)  # Time to First Token
    tpop = Column(Float)  # Time per Output Token
    throughput = Column(Float)
    success_rate = Column(Float)
    error_count = Column(Integer, default=0)
    percentile_50 = Column(Float)
    percentile_90 = Column(Float)
    percentile_95 = Column(Float)
    percentile_99 = Column(Float)
    raw_metrics = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    task = relationship("PerfTestTask", back_populates="results")

