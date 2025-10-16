from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class UserModelConfigBase(BaseModel):
    name: str = Field(..., description="配置名称")
    type: str = Field(..., description="模型类型，例如 openai、siliconflow")
    base_url: str = Field(..., description="模型 API 地址")
    api_key: Optional[str] = Field(None, description="API 密钥")
    model_name: str = Field(..., description="模型名称")
    additional_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外参数")
    is_active: Optional[bool] = Field(default=True, description="是否启用")


class UserModelConfigCreate(UserModelConfigBase):
    pass


class UserModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    additional_params: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class UserModelConfigOut(UserModelConfigBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserRAGConfigBase(BaseModel):
    name: str = Field(..., description="配置名称")
    type: str = Field(..., description="RAG 类型，例如 dify_chatflow、ragflow")
    url: str = Field(..., description="RAG 接口地址")
    api_key: Optional[str] = Field(None, description="API 密钥")
    request_headers: Optional[Dict[str, Any]] = Field(default_factory=dict, description="请求头配置")
    request_template: Optional[Dict[str, Any]] = Field(default_factory=dict, description="请求体模板")
    response_path: Optional[str] = Field(None, description="响应数据路径")
    stream_event_field: Optional[str] = Field(None, description="流式事件字段")
    stream_event_value: Optional[str] = Field(None, description="流式事件取值")
    is_active: Optional[bool] = Field(default=True, description="是否启用")


class UserRAGConfigCreate(UserRAGConfigBase):
    pass


class UserRAGConfigUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    api_key: Optional[str] = None
    request_headers: Optional[Dict[str, Any]] = None
    request_template: Optional[Dict[str, Any]] = None
    response_path: Optional[str] = None
    stream_event_field: Optional[str] = None
    stream_event_value: Optional[str] = None
    is_active: Optional[bool] = None


class UserRAGConfigOut(UserRAGConfigBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
