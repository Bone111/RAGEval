"""
模型配置模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, JSON
from datetime import datetime
import uuid

from app.db.base import Base
from app.models.types import StringUUID


class ModelConfig(Base):
    """模型配置"""
    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(StringUUID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    model_id = Column(String(255), nullable=False)
    model_name = Column(String(255), nullable=True)
    model_type = Column(String(50), default='local')  # local, api, modelscope, huggingface
    model_path = Column(String(500), nullable=True)
    api_url = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    model_args = Column(JSON, default={})
    generation_config = Column(JSON, default={})
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DatasetCache(Base):
    """数据集缓存"""
    __tablename__ = "dataset_cache"

    id = Column(Integer, primary_key=True, index=True)
    dataset_name = Column(String(255), nullable=False, unique=True)
    dataset_type = Column(String(50), default='standard')
    category = Column(String(100), index=True)
    language = Column(String(50))
    num_samples = Column(Integer)
    cache_path = Column(String(500))
    download_status = Column(String(50), default='not_cached', index=True)
    size_mb = Column(Float)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    extra_metadata = Column(JSON, default={})

