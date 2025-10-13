"""
EvalScope评测相关的Pydantic schemas
"""
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime


class TaskCreate(BaseModel):
    """创建评测任务的请求模型"""
    task_name: str = Field(..., description="任务名称", min_length=1, max_length=200)
    model_id: str = Field(..., description="模型ID", min_length=1, max_length=200)
    datasets: List[str] = Field(..., description="数据集列表", min_items=1)
    model_args: Optional[Dict[str, Any]] = Field(default={}, description="模型参数")
    dataset_args: Optional[Dict[str, Any]] = Field(default={}, description="数据集参数")
    generation_config: Optional[Dict[str, Any]] = Field(default={}, description="生成配置")
    eval_backend: Optional[str] = Field(default="Native", description="评测后端")
    eval_type: Optional[str] = Field(default="openai_api", description="评测类型")
    limit: Optional[int] = Field(default=None, description="样本数量限制", ge=1, le=10000)
    user_model_config: Optional[Dict[str, Any]] = Field(default=None, description="用户自定义模型配置")
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, description="额外元数据")


class TaskUpdate(BaseModel):
    """更新任务的请求模型"""
    task_name: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[str] = Field(None)
    progress: Optional[int] = Field(None, ge=0, le=100)
    error_message: Optional[str] = Field(None)


class TaskResponse(BaseModel):
    """任务响应模型"""
    id: int
    user_id: str
    task_name: str
    model_id: str
    datasets: List[str]
    model_args: Dict[str, Any]
    dataset_args: Dict[str, Any]
    generation_config: Dict[str, Any]
    eval_backend: str
    eval_type: str
    status: str
    progress: int
    error_message: Optional[str]
    work_dir: Optional[str]
    extra_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    first_started_at: Optional[datetime]
    total_paused_duration: Optional[int] = 0
    effective_duration: Optional[int] = None  # 计算字段：有效执行时长
    
    class Config:
        from_attributes = True


class TaskDetail(TaskResponse):
    """任务详情模型（包含结果）"""
    results: Optional[List["EvalResultResponse"]] = []


class TaskList(BaseModel):
    """任务列表响应"""
    total: int
    tasks: List[TaskResponse]


class EvalResultResponse(BaseModel):
    """评测结果响应模型"""
    id: int
    task_id: int
    benchmark: str
    metric_name: str
    metric_value: Optional[float]
    category: Optional[str]
    subset_name: Optional[str]
    num_samples: Optional[int]
    raw_results: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


class BenchmarkInfo(BaseModel):
    """Benchmark信息"""
    name: str
    display_name: str
    description: str
    category: str
    language: Optional[str] = None
    num_samples: Optional[int] = None
    tags: List[str] = []
    cached: bool = False
    cache_status: str = "not_cached"
    download_progress: Optional[int] = None
    file_size: Optional[str] = None
    last_updated: Optional[str] = None
    cache_path: Optional[str] = None
    num_subsets: Optional[int] = None  # 子集数量


class BenchmarkListResponse(BaseModel):
    """Benchmark列表响应"""
    benchmarks: List[BenchmarkInfo]
    total: int


class BenchmarkStatus(BaseModel):
    """Benchmark下载状态"""
    name: str
    status: str  # not_cached, downloading, cached, error
    size_mb: Optional[float] = None
    progress: Optional[int] = None
    error_message: Optional[str] = None
    cached_at: Optional[datetime] = None


class BenchmarkDownloadRequest(BaseModel):
    """Benchmark下载请求"""
    benchmark_names: List[str] = Field(..., min_items=1)
    force_redownload: Optional[bool] = Field(default=False)


class BenchmarkDownloadResponse(BaseModel):
    """Benchmark下载响应"""
    success: bool
    message: str
    results: List[BenchmarkStatus]


# 更新前向引用
TaskDetail.model_rebuild()