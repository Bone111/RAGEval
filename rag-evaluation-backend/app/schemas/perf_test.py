"""
性能测试相关的Pydantic模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ========== 任务相关 ==========

class PerfTestCreate(BaseModel):
    """创建性能测试任务"""
    task_name: str = Field(..., description="任务名称")
    api_url: str = Field(..., description="API地址")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    model_name: Optional[str] = Field(default=None, description="模型名称")
    test_type: str = Field(default='single', description="测试类型: single/multi/speed_benchmark")
    parallel: Optional[int] = Field(default=10, description="并发数")
    number: Optional[int] = Field(default=100, description="请求数")
    parallel_configs: Optional[List[int]] = Field(default=None, description="多场景并发配置")
    number_configs: Optional[List[int]] = Field(default=None, description="多场景请求数配置")
    duration: Optional[int] = Field(default=None, description="持续时间(秒)")
    stream: bool = Field(default=False, description="是否使用流式输出")
    config: Optional[Dict[str, Any]] = Field(default={}, description="额外配置")


class PerfTestUpdate(BaseModel):
    """更新性能测试任务"""
    status: Optional[str] = None
    error_message: Optional[str] = None


class PerfTestResponse(BaseModel):
    """性能测试任务响应"""
    id: int
    user_id: str
    task_name: str
    api_url: str
    model_name: Optional[str]
    test_type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class PerfTestDetail(PerfTestResponse):
    """性能测试任务详细信息"""
    parallel_configs: List[int]
    number_configs: List[int]
    duration: Optional[int]
    stream: bool
    config: Dict[str, Any]
    extra_metadata: Dict[str, Any]
    results: Optional[List['PerfResultResponse']] = []

    class Config:
        from_attributes = True


# ========== 结果相关 ==========

class PerfResultResponse(BaseModel):
    """性能测试结果响应"""
    id: int
    task_id: int
    parallel: int
    number: int
    qps: Optional[float]
    avg_latency: Optional[float]
    ttft: Optional[float]
    tpop: Optional[float]
    throughput: Optional[float]
    success_rate: Optional[float]
    error_count: int
    percentile_50: Optional[float]
    percentile_90: Optional[float]
    percentile_95: Optional[float]
    percentile_99: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class PerfResultDetail(PerfResultResponse):
    """性能测试结果详细信息"""
    raw_metrics: Dict[str, Any]

    class Config:
        from_attributes = True


# ========== 批量查询 ==========

class PerfTestList(BaseModel):
    """性能测试任务列表"""
    total: int
    tasks: List[PerfTestResponse]


# ========== 实时指标 (WebSocket) ==========

class MetricsUpdate(BaseModel):
    """实时指标更新"""
    type: str = "metrics"
    task_id: int
    parallel: int
    completed: int
    total: int
    current_qps: Optional[float]
    current_latency: Optional[float]
    success_count: int
    error_count: int
    timestamp: datetime

