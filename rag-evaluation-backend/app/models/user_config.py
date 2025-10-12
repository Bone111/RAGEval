from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from datetime import datetime

from app.db.base import Base
from app.models.types import StringUUID


class UserModelConfig(Base):
    """用户大模型配置"""
    __tablename__ = "user_model_configs"

    id = Column(StringUUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(StringUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)  # 配置名称
    type = Column(String(50), nullable=False)   # openai, siliconflow, dify等
    base_url = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)
    model_name = Column(String(100), nullable=False)
    additional_params = Column(JSON, default={})  # 额外参数
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserRAGConfig(Base):
    """用户RAG系统配置"""
    __tablename__ = "user_rag_configs"

    id = Column(StringUUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(StringUUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)   # 配置名称
    type = Column(String(50), nullable=False)    # dify_chatflow, dify_flow, ragflow, custom等
    url = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=True)
    request_headers = Column(JSON, default={})
    request_template = Column(JSON, default={})
    response_path = Column(String(200), nullable=True)
    stream_event_field = Column(String(100), nullable=True)
    stream_event_value = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())