"""
動態選項生成 API 路由
解決前端硬編碼選項的問題，提供智能的上下文相關選項建議
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from services.agent import agent as unified_agent
from models.project_models import ProjectData

# 創建路由器
router = APIRouter()


class OptionsRequest(BaseModel):
    """選項生成請求模型"""

    missing_keys: List[str]
    project_data: Optional[Dict[str, Any]] = None
    context: Optional[str] = ""
    user_preferences: Optional[List[str]] = []


class OptionsResponse(BaseModel):
    """選項生成響應模型"""

    options: List[str]
    categories: Dict[str, List[str]]
    recommendations: List[str]
    reasoning: str


@router.post("/options/contextual", response_model=OptionsResponse)
async def generate_contextual_options(request: OptionsRequest):
    """
    生成上下文相關的動態選項
    基於缺失的關鍵字段和專案數據，智能生成最相關的選項建議
    """
    try:
        # 使用統一代理生成選項
        options = await _generate_smart_options(
            request.missing_keys, request.project_data, request.context
        )

        # 按類別組織選項
        categories = _categorize_options(options, request.missing_keys)

        # 生成推薦理由
        reasoning = _generate_recommendation_reasoning(
            request.missing_keys, request.project_data
        )

        return OptionsResponse(
            options=options,
            categories=categories,
            recommendations=_generate_recommendations(request.missing_keys),
            reasoning=reasoning,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成動態選項失敗: {str(e)}")


@router.post("/options/industry", response_model=List[str])
async def get_industry_options(context: str = ""):
    """獲取產業相關選項"""
    try:
        return _get_industry_options(context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取產業選項失敗: {str(e)}")


@router.post("/options/budget", response_model=List[str])
async def get_budget_options(industry: str = "", scale: str = ""):
    """獲取預算相關選項"""
    try:
        return _get_budget_options(industry, scale)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取預算選項失敗: {str(e)}")


@router.post("/options/audience", response_model=List[str])
async def get_audience_options(industry: str = "", campaign_type: str = ""):
    """獲取受眾相關選項"""
    try:
        return _get_audience_options(industry, campaign_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取受眾選項失敗: {str(e)}")


# ===== 私有輔助函數 =====


async def _generate_smart_options(
    missing_keys: List[str],
    project_data: Optional[Dict[str, Any]] = None,
    context: str = "",
) -> List[str]:
    """智能生成選項"""
    all_options = []

    for key in missing_keys:
        key_options = await _generate_options_for_key(key, project_data, context)
        all_options.extend(key_options)

    # 去重並限制數量
    unique_options = list(set(all_options))
    return unique_options[:20]  # 最多返回20個選項


async def _generate_options_for_key(
    key: str, project_data: Optional[Dict[str, Any]] = None, context: str = ""
) -> List[str]:
    """為特定關鍵字段生成選項"""

    # 根據關鍵字段類型生成選項
    if "產業" in key:
        return _get_industry_options(context)

    elif "預算" in key or "金額" in key:
        industry = _extract_industry_from_context(context, project_data)
        return _get_budget_options(industry)

    elif "受眾" in key or "目標" in key:
        industry = _extract_industry_from_context(context, project_data)
        campaign_type = _extract_campaign_type_from_context(context, project_data)
        return _get_audience_options(industry, campaign_type)

    elif "時間" in key or "日期" in key:
        return _get_timing_options()

    elif "媒體" in key or "渠道" in key:
        industry = _extract_industry_from_context(context, project_data)
        return _get_media_options(industry)

    elif "企劃類型" in key:
        return _get_planning_type_options()

    else:
        # 通用選項
        return _get_generic_options(key)


def _get_industry_options(context: str = "") -> List[str]:
    """獲取產業選項"""
    base_industries = [
        "科技產品",
        "軟體服務",
        "硬體設備",
        "AI/機器學習",
        "消費品",
        "美妝保養",
        "服飾配件",
        "食品飲料",
        "服務業",
        "教育培訓",
        "醫療健康",
        "金融服務",
        "製造業",
        "汽車工業",
        "建築工程",
        "能源環保",
        "媒體娛樂",
        "遊戲產業",
        "電商平台",
        "旅遊觀光",
    ]

    # 根據上下文過濾相關產業
    if context:
        context_lower = context.lower()
        if "科技" in context_lower or "數位" in context_lower:
            return [
                ind
                for ind in base_industries
                if "科技" in ind or "軟體" in ind or "AI" in ind
            ]
        elif "消費" in context_lower or "零售" in context_lower:
            return [
                ind
                for ind in base_industries
                if "消費" in ind or "美妝" in ind or "服飾" in ind
            ]
        elif "服務" in context_lower:
            return [
                ind
                for ind in base_industries
                if "服務" in ind or "教育" in ind or "醫療" in ind
            ]

    return base_industries


def _get_budget_options(industry: str = "", scale: str = "") -> List[str]:
    """獲取預算選項"""
    base_budgets = ["10萬以下", "10-50萬", "50-100萬", "100-500萬", "500萬以上"]

    # 根據產業調整預算範圍
    if industry:
        if "科技" in industry or "AI" in industry:
            return ["50-100萬", "100-500萬", "500萬以上", "1000萬以上"]
        elif "消費品" in industry or "美妝" in industry:
            return ["10-50萬", "50-100萬", "100-500萬"]
        elif "製造業" in industry or "汽車" in industry:
            return ["100-500萬", "500萬以上", "1000萬以上"]

    return base_budgets


def _get_audience_options(industry: str = "", campaign_type: str = "") -> List[str]:
    """獲取受眾選項"""
    base_audiences = [
        "18-24歲學生",
        "25-35歲上班族",
        "35-45歲主管",
        "45歲以上高層",
        "女性為主",
        "男性為主",
        "家庭用戶",
        "企業用戶",
        "年輕族群",
        "中產階級",
        "高收入族群",
        "大眾市場",
    ]

    # 根據產業和活動類型調整受眾
    if industry:
        if "科技" in industry:
            return ["25-35歲上班族", "35-45歲主管", "企業用戶", "年輕族群"]
        elif "美妝" in industry:
            return ["18-24歲學生", "25-35歲上班族", "女性為主", "年輕族群"]
        elif "金融" in industry:
            return ["35-45歲主管", "45歲以上高層", "高收入族群", "企業用戶"]

    return base_audiences


def _get_timing_options() -> List[str]:
    """獲取時間相關選項"""
    return [
        "1個月內",
        "1-3個月",
        "3-6個月",
        "6個月以上",
        "即時執行",
        "短期活動",
        "長期策略",
        "季節性活動",
    ]


def _get_media_options(industry: str = "") -> List[str]:
    """獲取媒體渠道選項"""
    base_media = [
        "社群媒體",
        "搜尋引擎",
        "內容行銷",
        "影響者合作",
        "電視廣告",
        "廣播廣告",
        "戶外廣告",
        "印刷媒體",
        "電子郵件",
        "簡訊行銷",
        "應用程式",
        "網站",
    ]

    # 根據產業調整媒體選項
    if industry:
        if "科技" in industry:
            return [
                "社群媒體",
                "搜尋引擎",
                "內容行銷",
                "影響者合作",
                "網站",
                "應用程式",
            ]
        elif "消費品" in industry:
            return ["社群媒體", "電視廣告", "影響者合作", "戶外廣告", "電子郵件"]

    return base_media


def _get_planning_type_options() -> List[str]:
    """獲取企劃類型選項"""
    return [
        "數位行銷",
        "品牌行銷",
        "產品行銷",
        "活動行銷",
        "內容行銷",
        "社群行銷",
        "影響者行銷",
        "搜尋引擎行銷",
        "電子郵件行銷",
        "簡訊行銷",
        "電視廣告",
        "戶外廣告",
    ]


def _get_generic_options(key: str) -> List[str]:
    """獲取通用選項"""
    return [
        "請提供更多資訊",
        "需要進一步了解",
        "請具體說明",
        "請選擇最適合的",
        "請描述您的需求",
    ]


def _extract_industry_from_context(
    context: str, project_data: Optional[Dict[str, Any]] = None
) -> str:
    """從上下文或專案數據中提取產業信息"""
    if project_data and project_data.get("project_attributes", {}).get("industry"):
        return project_data["project_attributes"]["industry"]

    if context:
        context_lower = context.lower()
        if "科技" in context_lower:
            return "科技產品"
        elif "消費" in context_lower:
            return "消費品"
        elif "服務" in context_lower:
            return "服務業"
        elif "製造" in context_lower:
            return "製造業"

    return ""


def _extract_campaign_type_from_context(
    context: str, project_data: Optional[Dict[str, Any]] = None
) -> str:
    """從上下文或專案數據中提取活動類型"""
    if project_data and project_data.get("content_strategy", {}).get("planning_types"):
        types = project_data["content_strategy"]["planning_types"]
        if isinstance(types, list) and types:
            return types[0]
        return types

    if context:
        context_lower = context.lower()
        if "數位" in context_lower:
            return "數位行銷"
        elif "品牌" in context_lower:
            return "品牌行銷"
        elif "產品" in context_lower:
            return "產品行銷"

    return ""


def _categorize_options(
    options: List[str], missing_keys: List[str]
) -> Dict[str, List[str]]:
    """將選項按類別組織"""
    categories = {}

    for key in missing_keys:
        if "產業" in key:
            categories["產業"] = [
                opt
                for opt in options
                if any(ind in opt for ind in ["科技", "消費", "服務", "製造"])
            ]
        elif "預算" in key:
            categories["預算"] = [
                opt
                for opt in options
                if any(budget in opt for budget in ["萬", "千", "元"])
            ]
        elif "受眾" in key:
            categories["受眾"] = [
                opt
                for opt in options
                if any(audience in opt for audience in ["歲", "族群", "用戶"])
            ]
        elif "時間" in key:
            categories["時間"] = [
                opt
                for opt in options
                if any(time in opt for time in ["月", "年", "即時"])
            ]
        else:
            categories[key] = [
                opt for opt in options if opt not in sum(categories.values(), [])
            ]

    return categories


def _generate_recommendations(missing_keys: List[str]) -> List[str]:
    """生成推薦建議"""
    recommendations = []

    for key in missing_keys:
        if "產業" in key:
            recommendations.append("建議選擇與您業務最相關的產業類型")
        elif "預算" in key:
            recommendations.append("根據專案規模和目標選擇合適的預算範圍")
        elif "受眾" in key:
            recommendations.append("明確目標受眾有助於制定精準的行銷策略")
        elif "時間" in key:
            recommendations.append("設定合理的時間框架確保專案順利執行")
        else:
            recommendations.append(f"請提供關於 {key} 的具體資訊")

    return recommendations


def _generate_recommendation_reasoning(
    missing_keys: List[str], project_data: Optional[Dict[str, Any]] = None
) -> str:
    """生成推薦理由"""
    if not missing_keys:
        return "您的專案資訊已經完整，可以開始制定詳細的行銷策略。"

    reasoning_parts = []

    if "產業" in str(missing_keys):
        reasoning_parts.append("產業類型決定了行銷策略的方向和渠道選擇")

    if "預算" in str(missing_keys):
        reasoning_parts.append("預算規模影響活動的範圍和媒體組合")

    if "受眾" in str(missing_keys):
        reasoning_parts.append("目標受眾分析是制定有效行銷策略的基礎")

    if "時間" in str(missing_keys):
        reasoning_parts.append("時間安排影響活動的節奏和資源分配")

    if reasoning_parts:
        return (
            "建議優先補充以下資訊："
            + "；".join(reasoning_parts)
            + "。這些資訊將幫助我們制定更精準和有效的行銷策略。"
        )

    return "請提供更多專案細節，我將為您生成最適合的選項建議。"
