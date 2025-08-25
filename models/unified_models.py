#!/usr/bin/env python3
"""
統一的數據模型
整合企劃案和受眾分析的數據結構
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
from enum import Enum


class MessageRole(str, Enum):
    """訊息角色"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(str, Enum):
    """訊息類型"""

    TEXT = "text"
    OPTIONS = "options"
    PROJECT_UPDATE = "project_update"
    AUDIENCE_INSIGHT = "audience_insight"
    CLARIFICATION = "clarification"


class ProjectAttributes(BaseModel):
    """專案屬性"""

    industry: Optional[str] = Field(None, description="產業")
    campaign: Optional[str] = Field(None, description="活動主題")
    objective: Optional[str] = Field(None, description="企劃目標")
    is_urgent: Optional[bool] = Field(None, description="是否急案")
    description: Optional[str] = Field(None, description="專案描述")


class TimeBudget(BaseModel):
    """時間和預算"""

    planning_due_date: Optional[str] = Field(None, description="提案交付日期")
    campaign_start_date: Optional[str] = Field(None, description="活動開始日期")
    campaign_end_date: Optional[str] = Field(None, description="活動結束日期")
    budget: Optional[str] = Field(None, description="預算金額")


class ContentStrategy(BaseModel):
    """內容策略"""

    planning_types: Optional[List[str]] = Field(None, description="企劃類型")
    media_formats: Optional[List[str]] = Field(None, description="媒體/投放形式")
    audience_lock: Optional[str] = Field(None, description="受眾鎖定")
    audience_behavior: Optional[str] = Field(None, description="受眾行為")
    client_materials: Optional[str] = Field(None, description="客戶素材")
    client_requests: Optional[str] = Field(None, description="客戶要求")


class TechnicalNeeds(BaseModel):
    """技術需求"""

    technical_needs: Optional[str] = Field(None, description="技術需求")
    platform_requirements: Optional[List[str]] = Field(None, description="平台需求")
    integration_needs: Optional[List[str]] = Field(None, description="整合需求")


class AudienceInsights(BaseModel):
    """受眾洞察"""

    target_demographics: Optional[Dict[str, Any]] = Field(
        None, description="目標人口統計"
    )
    psychographic_profile: Optional[Dict[str, Any]] = Field(
        None, description="心理特徵檔案"
    )
    behavior_patterns: Optional[List[str]] = Field(None, description="行為模式")
    pain_points: Optional[List[str]] = Field(None, description="痛點")
    motivations: Optional[List[str]] = Field(None, description="動機")
    media_preferences: Optional[List[str]] = Field(None, description="媒體偏好")


class ProjectData(BaseModel):
    """統一的專案數據"""

    project_attributes: ProjectAttributes = Field(default_factory=ProjectAttributes)
    time_budget: TimeBudget = Field(default_factory=TimeBudget)
    content_strategy: ContentStrategy = Field(default_factory=ContentStrategy)
    technical_needs: TechnicalNeeds = Field(default_factory=TechnicalNeeds)
    audience_insights: AudienceInsights = Field(default_factory=AudienceInsights)

    # 元數據
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completeness_score: float = Field(0.0, description="完整度分數")
    status: str = Field("draft", description="狀態")


class ChatMessage(BaseModel):
    """聊天訊息"""

    role: MessageRole
    content: str
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = Field(None, description="額外元數據")


class QuickReply(BaseModel):
    """快速回覆選項"""

    text: str
    value: str
    category: Optional[str] = Field(None, description="分類")
    priority: int = Field(1, description="優先級")


class ChatTurnRequest(BaseModel):
    """聊天回合請求"""
    message: Optional[str] = None
    session_id: Optional[str]
    intent: Optional[str] = Field(None, description="意圖名稱")
    params: Optional[Dict[str, Any]] = Field(None, description="意圖參數")
    attachments: Optional[List[Dict[str, Any]]] = Field(
        None, description="附件資訊"
    )
    project_data: Optional[ProjectData] = Field(None, description="現有專案數據")


class ChatTurnResponse(BaseModel):
    """聊天回合回應"""

    message: str
    session_id: str
    project_data: ProjectData
    quick_replies: List[QuickReply] = Field(default_factory=list)
    contextual_options: Optional[Dict[str, List[str]]] = Field(
        None, description="上下文相關選項"
    )
    next_action: Optional[str] = Field(None, description="建議的下一步動作")
    is_complete: bool = Field(False, description="專案是否完整")
    completeness_score: float = Field(0.0, description="完整度分數")
    data: Optional[Dict[str, Any]] = Field(None, description="額外資料")


class Section(BaseModel):
    id: str
    title: str
    body: str


class SixChapterReport(BaseModel):
    sections: List[Section]

    @validator("sections")
    def must_have_six(cls, v: List[Section]):
        ids = [s.id for s in v]
        assert ids == [
            "macro",
            "buzz",
            "competitors",
            "brand",
            "audience",
            "insight",
        ]
        return v


class SessionData(BaseModel):
    """會話數據"""

    session_id: str
    user_id: Optional[str] = Field(None, description="用戶ID")
    project_data: ProjectData = Field(default_factory=ProjectData)
    chat_history: List[ChatMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: str = Field("active", description="會話狀態")


class AgentOutput(BaseModel):
    """代理輸出"""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = Field(None, description="輸出數據")
    project_data: Optional[ProjectData] = Field(None, description="專案數據")
    quick_replies: Optional[List[QuickReply]] = Field(None, description="快速回覆選項")
    next_action: Optional[str] = Field(None, description="下一步動作")


class ToolResult(BaseModel):
    """工具執行結果"""

    success: bool
    data: Any
    message: str
    metadata: Optional[Dict[str, Any]] = Field(None, description="元數據")
