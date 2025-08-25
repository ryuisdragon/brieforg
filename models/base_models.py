"""
基礎模型定義
整合所有重複的基礎模型，提供統一的接口
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BaseRequest(BaseModel):
    """統一的基礎請求模型"""

    user_id: str = "guest"
    session_id: Optional[str] = None


class BaseResponse(BaseModel):
    """統一的基礎響應模型"""

    status: str = "success"
    message: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class IntakeRequest(BaseRequest):
    """統一的項目需求請求模型"""

    requirement: str = Field(..., description="項目需求描述")

    class Config:
        schema_extra = {
            "example": {
                "requirement": "我們需要為新產品設計一個數位行銷活動",
                "user_id": "user123",
                "session_id": "session456",
            }
        }


class ClarifyRequest(BaseRequest):
    """統一的項目澄清請求模型"""

    original_requirement: str = Field(..., description="原始需求描述")
    clarification_answers: List[str] = Field(..., description="澄清問題的回答")

    class Config:
        schema_extra = {
            "example": {
                "original_requirement": "我們需要為新產品設計一個數位行銷活動",
                "clarification_answers": ["科技產品", "25-35歲上班族", "100萬預算"],
                "user_id": "user123",
                "session_id": "session456",
            }
        }


# 移除重複的模型定義：
# - IntakeRequest (line 99) -> 使用統一的 IntakeRequest
# - ClarifyRequest (line 104) -> 使用統一的 ClarifyRequest
# - ProjectIntakeRequest (line 110) -> 使用統一的 IntakeRequest
# - ProjectClarifyRequest (line 115) -> 使用統一的 ClarifyRequest

