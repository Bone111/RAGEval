from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class ReportBase(BaseModel):
    title: str
    description: Optional[str] = None
    report_type: str  # evaluation, performance, comparison
    public: bool = False
    config: Optional[Dict[str, Any]] = None

class ReportCreate(ReportBase):
    project_id: str

class ReportUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    public: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None

class Report(ReportBase):
    id: str
    user_id: str
    project_id: str
    content: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
