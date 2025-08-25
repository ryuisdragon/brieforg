"""
聊天相關模型定義
整合重複的聊天模型，提供統一的會話管理接口
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatSession(BaseModel):
    """統一的聊天會話模型"""

    session_id: str
    user_id: str
    original_requirement: str
    answers: List[str] = Field(default_factory=list)
    asked_questions: List[str] = Field(default_factory=list)
    last_question: Optional[str] = None
    completeness_score: float = 0.0
    missing_keys: List[str] = Field(default_factory=list)
    has_pending_confirmation: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    planning_project: Optional[Dict[str, Any]] = None
    proposal_text: Optional[str] = None
    project_data: Optional[Dict[str, Any]] = None

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session123",
                "user_id": "user456",
                "original_requirement": "數位行銷活動企劃",
                "answers": ["科技產品", "25-35歲上班族"],
                "asked_questions": ["請描述您的產業", "目標受眾是誰"],
                "completeness_score": 0.6,
                "missing_keys": ["預算", "活動時間"],
            }
        }


class ChatMessage(BaseModel):
    """統一的聊天消息模型"""

    message: str = ""
    user_id: str = "guest"
    session_id: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "message": "我們需要為新產品設計數位行銷活動",
                "user_id": "user123",
                "session_id": "session456",
            }
        }


class ChatTurnResponse(BaseModel):
    """統一的聊天回應模型"""

    session_id: str
    role: str
    message: str
    status: str
    completeness_score: float
    missing_keys: List[str]
    asked_questions: List[str]
    next_question: Optional[str] = None
    planning_project: Optional[Dict[str, Any]] = None
    proposal_text: Optional[str] = None
    quick_replies: Optional[List[str]] = None
    quick_actions: Optional[List[Dict[str, Any]]] = None

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session123",
                "role": "assistant",
                "message": "請告訴我您的產業類型",
                "status": "need_clarification",
                "completeness_score": 0.3,
                "missing_keys": ["產業", "預算", "時間"],
                "asked_questions": ["請描述您的產業"],
                "next_question": "您的預算是多少？",
            }
        }


# 移除重複的模型定義：
# - ChatTurnResponse (line 145) -> 使用統一的 ChatTurnResponse
# - ChatTurnResponse (line 2932) -> 使用統一的 ChatTurnResponse

