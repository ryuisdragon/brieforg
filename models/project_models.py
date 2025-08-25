"""
專案相關模型定義
整合專案數據結構和相關模型
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProjectAttributes(BaseModel):
    """專案屬性模型"""

    industry: Optional[str] = "待確認"
    campaign: Optional[str] = "待確認"
    is_urgent: Optional[bool] = None


class TimeBudget(BaseModel):
    """時間預算模型"""

    planning_due_date: Optional[str] = None
    campaign_start_date: Optional[str] = None
    campaign_end_date: Optional[str] = None
    budget: Optional[str] = None


class ContentStrategy(BaseModel):
    """內容策略模型"""

    planning_types: Optional[List[str]] = None
    media_formats: Optional[List[str]] = None
    audience_lock: Optional[str] = None
    audience_behavior: Optional[Dict[str, Any]] = None
    client_materials: Optional[str] = None
    client_requests: Optional[str] = None


class TechnicalNeeds(BaseModel):
    """技術需求模型"""

    technical_needs: Optional[str] = None


class ProjectData(BaseModel):
    """統一的專案數據模型"""

    project_attributes: Optional[ProjectAttributes] = None
    time_budget: Optional[TimeBudget] = None
    content_strategy: Optional[ContentStrategy] = None
    technical_needs: Optional[TechnicalNeeds] = None

    class Config:
        schema_extra = {
            "example": {
                "project_attributes": {
                    "industry": "科技產品",
                    "campaign": "新產品上市行銷",
                    "is_urgent": False,
                },
                "time_budget": {
                    "planning_due_date": "2024-03-01",
                    "campaign_start_date": "2024-03-15",
                    "campaign_end_date": "2024-04-15",
                    "budget": "100萬",
                },
                "content_strategy": {
                    "planning_types": ["數位行銷", "社群媒體"],
                    "media_formats": ["影片", "圖片", "文字"],
                    "audience_lock": "25-35歲上班族",
                },
            }
        }


class ProjectRequest(BaseModel):
    """專案請求模型"""

    requirement: str = Field(..., description="專案需求描述")
    user_id: str = "guest"
    session_id: Optional[str] = None


class ProjectResponse(BaseModel):
    """專案響應模型"""

    project_data: ProjectData
    completeness_score: float
    missing_keys: List[str]
    status: str = "success"
    message: str = ""

