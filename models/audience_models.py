"""
受眾相關模型定義
整合受眾分析和策略相關的模型
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AudienceBehavior(BaseModel):
    """受眾行為模型"""

    scenarios: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    demographic: Optional[Dict[str, Any]] = None
    exclusions: Optional[List[str]] = None
    keywords: Optional[List[str]] = None


class AudienceInsights(BaseModel):
    """受眾洞察模型"""

    behavior_patterns: List[str] = Field(default_factory=list)
    interest_analysis: str = ""
    consumption_habits: str = ""
    media_preferences: List[str] = Field(default_factory=list)
    competitor_audience: str = ""
    reach_strategy: str = ""
    recommendations: List[str] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "behavior_patterns": ["喜歡在社群媒體分享", "習慣線上購物"],
                "interest_analysis": "對科技創新產品有高度興趣",
                "consumption_habits": "願意為品質支付溢價",
                "media_preferences": ["Instagram", "YouTube", "LinkedIn"],
                "competitor_audience": "與競品受眾重疊度較高",
                "reach_strategy": "透過影響者合作觸達目標受眾",
            }
        }


class AudienceStrategy(BaseModel):
    """受眾策略模型"""

    targeting_strategy: str = ""
    channel_mix: List[str] = Field(default_factory=list)
    content_strategy: str = ""
    timing_recommendations: str = ""
    budget_allocation: str = ""
    kpi_metrics: List[str] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "targeting_strategy": "精準定位25-35歲科技愛好者",
                "channel_mix": ["社群媒體", "搜尋引擎", "內容行銷"],
                "content_strategy": "以教育性和娛樂性內容為主",
                "timing_recommendations": "週間晚上8-10點投放",
                "budget_allocation": "社群媒體40%, 搜尋30%, 內容30%",
                "kpi_metrics": ["點擊率", "轉換率", "品牌知名度"],
            }
        }


class AudienceCoachState(BaseModel):
    """受眾教練狀態模型"""

    session_id: str
    user_id: str
    original_requirement: str
    current_project_data: Optional[Dict[str, Any]] = None
    audience_insights: Optional[AudienceInsights] = None
    audience_strategy: Optional[AudienceStrategy] = None
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    current_question: Optional[str] = None
    completeness_score: float = 0.0
    missing_audience_info: List[str] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

