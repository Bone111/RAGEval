from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class VLMTaskCreate(BaseModel):
    """创建VLM任务的请求模型"""
    task_name: str = Field(..., description="任务名称")
    model_id: str = Field(..., description="模型ID或路径")
    datasets: List[str] = Field(..., description="数据集列表")
    
    # VLM特定配置
    model_type: Optional[str] = Field("local", description="模型类型: local, api, custom")
    api_base: Optional[str] = Field(None, description="API基础地址")
    api_key: Optional[str] = Field(None, description="API密钥")
    model_path: Optional[str] = Field(None, description="本地模型路径")
    
    # 评测配置
    eval_backend: str = Field("VLMEvalKit", description="评测后端")
    limit: Optional[int] = Field(50, description="每个数据集的样本限制")
    nproc: Optional[int] = Field(1, description="并行进程数")
    temperature: Optional[float] = Field(0.0, description="生成温度")
    max_tokens: Optional[int] = Field(1024, description="最大Token数")
    reuse_cache: Optional[bool] = Field(True, description="是否复用缓存")
    
    # 额外配置
    extra_config: Optional[Dict[str, Any]] = Field(None, description="额外配置信息")

    class Config:
        json_schema_extra = {
            "example": {
                "task_name": "Qwen-VL多模态评测",
                "model_id": "qwen-vl-chat",
                "datasets": ["MMBench_DEV_EN", "MME", "SEEDBench_IMG"],
                "model_type": "local",
                "limit": 50,
                "temperature": 0.0,
                "max_tokens": 1024
            }
        }


class VLMTaskResponse(BaseModel):
    """VLM任务响应模型"""
    id: str
    user_id: str
    task_name: str
    model_id: str
    datasets: List[str]
    status: str
    progress: int
    
    # VLM配置
    model_type: Optional[str]
    model_path: Optional[str]
    api_base: Optional[str]
    eval_backend: str
    limit: Optional[int]
    nproc: int
    temperature: float
    max_tokens: int
    reuse_cache: bool
    
    # 执行信息
    work_dir: Optional[str]
    celery_task_id: Optional[str]
    error_message: Optional[str]
    
    # 时间戳
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class VLMResultResponse(BaseModel):
    """VLM评测结果响应模型"""
    id: str
    task_id: str
    dataset: str
    metric_name: str
    metric_value: Optional[float]
    category: Optional[str]
    subset_name: Optional[str]
    num_samples: Optional[int]
    accuracy: Optional[float]
    raw_results: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class VLMTaskDetail(VLMTaskResponse):
    """VLM任务详情（包含结果）"""
    results: List[VLMResultResponse] = []

    class Config:
        from_attributes = True


class VLMDatasetInfo(BaseModel):
    """VLM数据集信息"""
    name: str
    display_name: str
    description: str
    category: str
    language: str
    num_samples: Optional[int]
    supported_metrics: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "name": "MMBench_DEV_EN",
                "display_name": "MMBench Development (English)",
                "description": "Multi-modal benchmark for perception and reasoning",
                "category": "综合理解",
                "language": "en",
                "num_samples": 2974,
                "supported_metrics": ["accuracy", "score"]
            }
        }


class VLMModelInfo(BaseModel):
    """VLM模型信息"""
    name: str
    display_name: str
    description: str
    model_type: str
    supported_modalities: List[str]
    max_tokens: int
    requires_api_key: bool

    class Config:
        json_schema_extra = {
            "example": {
                "name": "qwen-vl-chat",
                "display_name": "Qwen-VL-Chat",
                "description": "通义千问视觉语言模型",
                "model_type": "local",
                "supported_modalities": ["text", "image"],
                "max_tokens": 2048,
                "requires_api_key": False
            }
        }


class VLMTaskStats(BaseModel):
    """VLM任务统计信息"""
    total_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    average_duration_minutes: Optional[float]
    popular_datasets: List[Dict[str, Any]]
    popular_models: List[Dict[str, Any]]

    class Config:
        json_schema_extra = {
            "example": {
                "total_tasks": 25,
                "running_tasks": 2,
                "completed_tasks": 20,
                "failed_tasks": 3,
                "average_duration_minutes": 45.5,
                "popular_datasets": [
                    {"name": "MMBench_DEV_EN", "usage_count": 15},
                    {"name": "MME", "usage_count": 12}
                ],
                "popular_models": [
                    {"name": "qwen-vl-chat", "usage_count": 10},
                    {"name": "llava-v1.5-7b", "usage_count": 8}
                ]
            }
        }


