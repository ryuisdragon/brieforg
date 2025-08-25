#!/usr/bin/env python3
"""
狀態機硬控流程模型
實現固定的槽位收集流程，替代LLM自選流程
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class SlotKey(str, Enum):
    """槽位鍵值枚舉"""

    INDUSTRY = "industry"
    OBJECTIVE = "objective"
    AUDIENCE_TARGETING = "audience_targeting"
    CAMPAIGN_THEME = "campaign_theme"
    CAMPAIGN_PERIOD = "campaign_period"
    TOTAL_BUDGET_TWD = "total_budget_twd"
    MEDIA_FORMATS = "media_formats"
    PLAN_TYPE = "plan_type"


class SlotStatus(str, Enum):
    """槽位狀態"""

    EMPTY = "empty"
    FILLED = "filled"
    OPTIONAL = "optional"


class SlotData(BaseModel):
    """槽位數據模型"""

    key: SlotKey
    value: Optional[Any] = None
    status: SlotStatus = SlotStatus.EMPTY
    required: bool = True
    validation_rules: Optional[Dict[str, Any]] = None


class SuggestionBubble(BaseModel):
    """建議泡泡模型"""

    label: str
    slot: SlotKey
    value: str
    send_as_user: str


class RationaleCard(BaseModel):
    """理由卡片模型（僅在theme時必回）"""

    title: str
    bullets: List[str] = Field(..., min_items=1, max_items=3)


class StateMachineOutput(BaseModel):
    """狀態機輸出合約"""

    message: str = Field(..., max_length=100, description="兩句洞察＋問句，≤100字")
    next_question: str = Field(..., description="問句式")
    suggestions: List[SuggestionBubble] = Field(
        ..., min_items=3, max_items=5, description="3-5顆，點即送"
    )
    slot_writes: Optional[Dict[str, Any]] = Field(None, description="同步直寫（可選）")
    rationale_cards: Optional[List[RationaleCard]] = Field(
        None, description="理由卡片（僅在theme時必回）"
    )
    missing_keys: List[str] = Field(
        default_factory=list, description="伺服端計算，用於待補欄位"
    )
    completion: float = Field(0.0, ge=0.0, le=1.0, description="完成度")


class ProjectSlots(BaseModel):
    """專案槽位集合"""

    industry: Optional[str] = None
    objective: Optional[str] = None
    audience_targeting: Optional[str] = None
    campaign_theme: Optional[str] = None
    campaign_period: Optional[Dict[str, str]] = None  # {start, end}
    total_budget_twd: Optional[int] = None  # 台幣單一數字
    media_formats: Optional[List[str]] = None  # 限白名單
    plan_type: Optional[str] = None

    # 可選欄位
    sub_industry: Optional[str] = None  # 子產業/產品線

    class Config:
        use_enum_values = True


# 硬控流程順序
SLOT_ORDER: List[SlotKey] = [
    SlotKey.INDUSTRY,
    SlotKey.OBJECTIVE,
    SlotKey.AUDIENCE_TARGETING,
    SlotKey.CAMPAIGN_THEME,
    SlotKey.CAMPAIGN_PERIOD,
    SlotKey.TOTAL_BUDGET_TWD,
    SlotKey.MEDIA_FORMATS,
    SlotKey.PLAN_TYPE,
]

# 媒體格式白名單
MEDIA_FORMATS_WHITELIST = ["社群", "搜尋", "影音", "OOH", "KOL"]

# 企劃類型選項
PLAN_TYPE_OPTIONS = [
    "前端洞察分析",
    "策略提案",
    "產品包裝",
    "市場趨勢分析",
    "創意版位製作",
    "文案撰寫",
]


def is_slot_filled(slot_key: SlotKey, slots: ProjectSlots) -> bool:
    """檢查槽位是否已填充"""
    if slot_key == SlotKey.CAMPAIGN_PERIOD:
        return bool(
            slots.campaign_period
            and slots.campaign_period.get("start")
            and slots.campaign_period.get("end")
        )

    elif slot_key == SlotKey.TOTAL_BUDGET_TWD:
        return isinstance(slots.total_budget_twd, int) and slots.total_budget_twd > 0

    elif slot_key == SlotKey.MEDIA_FORMATS:
        return isinstance(slots.media_formats, list) and len(slots.media_formats) > 0

    else:
        value = getattr(slots, slot_key.value, None)
        if isinstance(value, list):
            return len(value) > 0
        return bool(value)


def get_next_slot(slots: ProjectSlots) -> Union[SlotKey, str]:
    """獲取下一個需要填充的槽位"""
    for slot_key in SLOT_ORDER:
        if not is_slot_filled(slot_key, slots):
            return slot_key
    return "done"


def calculate_completion(slots: ProjectSlots) -> float:
    """計算完成度"""
    total_slots = len(SLOT_ORDER)
    filled_slots = sum(1 for slot in SLOT_ORDER if is_slot_filled(slot, slots))
    return filled_slots / total_slots


def get_missing_keys(slots: ProjectSlots) -> List[str]:
    """獲取缺失的槽位鍵值"""
    return [slot.value for slot in SLOT_ORDER if not is_slot_filled(slot, slots)]


def validate_slot_value(slot_key: SlotKey, value: Any) -> bool:
    """驗證槽位值"""
    if slot_key == SlotKey.MEDIA_FORMATS:
        if not isinstance(value, list):
            return False
        return all(item in MEDIA_FORMATS_WHITELIST for item in value)

    elif slot_key == SlotKey.TOTAL_BUDGET_TWD:
        return isinstance(value, int) and value > 0

    elif slot_key == SlotKey.CAMPAIGN_PERIOD:
        if not isinstance(value, dict):
            return False
        return "start" in value and "end" in value

    elif slot_key == SlotKey.PLAN_TYPE:
        return value in PLAN_TYPE_OPTIONS

    return True
