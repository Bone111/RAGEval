from sqlalchemy import Column, String, Text, DateTime, Integer, Float, JSON, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.types import StringUUID
from datetime import datetime, timezone
import uuid


def utc_now():
    """返回带时区信息的UTC时间"""
    return datetime.now(timezone.utc)


class VLMTask(Base):
    """VLM多模态评测任务表"""
    __tablename__ = "vlm_tasks"

    id = Column(StringUUID, primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    user_id = Column(StringUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_name = Column(String(200), nullable=False)
    model_id = Column(String(100), nullable=False)  # 模型标识符或路径
    datasets = Column(JSON, nullable=False)  # 评测数据集列表
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed, cancelled
    progress = Column(Integer, default=0)  # 0-100
    
    # VLM特定配置
    model_type = Column(String(50), nullable=True)  # local, api, custom
    api_base = Column(String(500), nullable=True)  # API地址
    api_key_hash = Column(String(200), nullable=True)  # API密钥哈希
    model_path = Column(String(500), nullable=True)  # 本地模型路径
    
    # 评测配置
    eval_backend = Column(String(50), default="VLMEvalKit")
    limit = Column(Integer, nullable=True)  # 每个数据集的样本限制
    nproc = Column(Integer, default=1)  # 并行进程数
    temperature = Column(Float, default=0.0)
    max_tokens = Column(Integer, default=1024)
    reuse_cache = Column(Boolean, default=True)
    
    # 额外配置信息
    extra_config = Column(JSON, nullable=True)
    
    # 执行信息
    work_dir = Column(String(500), nullable=True)  # 工作目录
    celery_task_id = Column(String(100), nullable=True)  # Celery任务ID
    error_message = Column(Text, nullable=True)
    log_content = Column(Text, nullable=True)
    
    # 时间戳
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # 关系
    results = relationship("VLMResult", back_populates="task", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<VLMTask(id={self.id}, name='{self.task_name}', status='{self.status}')>"


class VLMResult(Base):
    """VLM评测结果表"""
    __tablename__ = "vlm_results"

    id = Column(StringUUID, primary_key=True, default=uuid.uuid4, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    task_id = Column(StringUUID, ForeignKey("vlm_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset = Column(String(100), nullable=False)  # 数据集名称
    metric_name = Column(String(100), nullable=False)  # 指标名称
    metric_value = Column(Float, nullable=True)  # 指标值
    
    # VLM特定字段
    category = Column(String(100), nullable=True)  # 评测类别
    subset_name = Column(String(100), nullable=True)  # 子集名称
    num_samples = Column(Integer, nullable=True)  # 样本数量
    accuracy = Column(Float, nullable=True)  # 准确率
    
    # 详细结果信息
    raw_results = Column(JSON, nullable=True)  # 原始结果数据
    sample_results = Column(JSON, nullable=True)  # 样本级别结果
    
    # 关系
    task = relationship("VLMTask", back_populates="results")

    def __repr__(self):
        return f"<VLMResult(task_id={self.task_id}, dataset='{self.dataset}', metric='{self.metric_name}')>"
