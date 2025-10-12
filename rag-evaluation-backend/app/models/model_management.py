"""
大模型统一管理数据模型
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey, Text, BigInteger
from sqlalchemy import JSON, UUID as PG_UUID
from datetime import datetime
import uuid

from app.db.base import Base
from app.models.types import StringUUID


class ModelInfo(Base):
    """大模型信息表 - 统一管理所有模型信息"""
    __tablename__ = "model_info"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(StringUUID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
    # 基础信息
    model_id = Column(String(255), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)  # 用户自定义显示名称
    model_type = Column(String(50), nullable=False, index=True)  # local, api, download, cloud
    model_source = Column(String(100), nullable=True)  # huggingface, modelscope, openai, ollama等
    
    # 模型详细信息
    model_family = Column(String(100), nullable=True)  # llama, qwen, gpt, etc
    model_size = Column(String(50), nullable=True)  # 7B, 13B, 70B, etc
    parameter_count = Column(BigInteger, nullable=True)  # 参数量
    model_version = Column(String(100), nullable=True)  # 模型版本
    
    # 路径和配置信息
    model_path = Column(String(1000), nullable=True)  # 本地路径或URL
    config_path = Column(String(1000), nullable=True)  # 配置文件路径
    tokenizer_path = Column(String(1000), nullable=True)  # tokenizer路径
    
    # API配置（如果是API模型）
    api_url = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    api_provider = Column(String(100), nullable=True)  # openai, anthropic, etc
    
    # 模型状态
    status = Column(String(50), default='unknown', index=True)  # available, downloading, error, offline
    download_progress = Column(Float, default=0.0)  # 下载进度 0-100
    file_size = Column(BigInteger, nullable=True)  # 文件大小（字节）
    disk_usage = Column(BigInteger, nullable=True)  # 磁盘占用（字节）
    
    # 性能信息
    supported_context_length = Column(Integer, nullable=True)  # 支持的上下文长度
    max_tokens = Column(Integer, nullable=True)  # 最大生成tokens
    inference_speed = Column(Float, nullable=True)  # 推理速度 tokens/s
    memory_usage = Column(BigInteger, nullable=True)  # 内存使用（字节）
    
    # 能力标签
    capabilities = Column(JSON, default=[])  # ['chat', 'code', 'math', 'multimodal']
    languages = Column(JSON, default=[])  # 支持的语言
    tags = Column(JSON, default=[])  # 用户标签
    
    # 使用统计
    usage_count = Column(Integer, default=0)  # 使用次数
    last_used_at = Column(DateTime, nullable=True)  # 最后使用时间
    
    # 评测信息
    benchmark_scores = Column(JSON, default={})  # 各项benchmark得分
    quality_rating = Column(Float, nullable=True)  # 质量评分 1-10
    
    # 系统信息
    is_active = Column(Boolean, default=True, index=True)
    is_favorite = Column(Boolean, default=False, index=True)  # 收藏
    notes = Column(Text, nullable=True)  # 用户备注
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_scanned_at = Column(DateTime, nullable=True)  # 最后扫描时间
    
    # 额外元数据
    extra_metadata = Column(JSON, default={})


class ModelUsageLog(Base):
    """模型使用日志表"""
    __tablename__ = "model_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(StringUUID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    model_id = Column(Integer, ForeignKey("model_info.id", ondelete="CASCADE"), index=True)
    
    # 使用信息
    usage_type = Column(String(50), nullable=False)  # chat, eval, generation, etc
    task_name = Column(String(255), nullable=True)  # 任务名称
    
    # 性能数据
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)  # 延迟毫秒
    throughput = Column(Float, nullable=True)  # tokens/s
    
    # 成本统计
    cost_estimate = Column(Float, nullable=True)  # 预估成本
    
    # 质量评估
    quality_score = Column(Float, nullable=True)  # 输出质量评分
    user_rating = Column(Integer, nullable=True)  # 用户评分 1-5
    
    # 时间信息
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 额外信息
    extra_data = Column(JSON, default={})


class ModelDownloadTask(Base):
    """模型下载任务表"""
    __tablename__ = "model_download_tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(StringUUID, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    
    # 下载信息
    model_name = Column(String(255), nullable=False)
    model_source = Column(String(100), nullable=False)  # huggingface, modelscope, etc
    source_url = Column(String(1000), nullable=False)  # 下载源URL
    local_path = Column(String(1000), nullable=True)  # 本地保存路径
    
    # 任务状态
    status = Column(String(50), default='pending', index=True)  # pending, downloading, completed, failed, cancelled
    progress = Column(Float, default=0.0)  # 下载进度 0-100
    
    # 文件信息
    total_size = Column(BigInteger, nullable=True)  # 总大小
    downloaded_size = Column(BigInteger, default=0)  # 已下载大小
    download_speed = Column(Float, nullable=True)  # 下载速度 bytes/s
    
    # 时间信息
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    estimated_completion = Column(DateTime, nullable=True)  # 预计完成时间
    
    # 错误信息
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # 系统信息
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 额外配置
    download_config = Column(JSON, default={})  # 下载配置


class LocalModelRegistry(Base):
    """本地模型注册表 - 扫描发现的本地模型"""
    __tablename__ = "local_model_registry"

    id = Column(Integer, primary_key=True, index=True)
    
    # 模型路径信息
    model_path = Column(String(1000), nullable=False, unique=True)
    model_name = Column(String(255), nullable=False)
    model_type = Column(String(50), nullable=True)  # 推断的模型类型
    
    # 文件信息
    file_size = Column(BigInteger, nullable=True)
    file_count = Column(Integer, nullable=True)
    config_files = Column(JSON, default=[])  # 配置文件列表
    
    # 扫描信息
    scan_status = Column(String(50), default='discovered')  # discovered, analyzed, registered, error
    last_modified = Column(DateTime, nullable=True)  # 文件最后修改时间
    last_scanned = Column(DateTime, default=datetime.utcnow)
    
    # 启用控制
    is_enabled = Column(Boolean, default=True)  # 是否启用，控制是否显示在模型列表中
    
    # 模型信息（从配置文件中提取）
    detected_info = Column(JSON, default={})  # 检测到的模型信息
    
    # 系统信息
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModelCategory(Base):
    """模型分类表"""
    __tablename__ = "model_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)
    color = Column(String(20), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ModelCategoryMapping(Base):
    """模型分类映射表"""
    __tablename__ = "model_category_mappings"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("model_info.id", ondelete="CASCADE"), index=True)
    category_id = Column(Integer, ForeignKey("model_categories.id", ondelete="CASCADE"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
