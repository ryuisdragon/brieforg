#!/usr/bin/env python3
"""
重構後的統一企劃需求助手服務
整合企劃專案管理和受眾分析功能
"""

import logging
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Dict, Any, Optional
import re
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from models.unified_models import (
    ChatTurnRequest,
    ChatTurnResponse,
    ProjectData,
    MessageRole,
)
from services.llm_client import LLMClient
from services.session import manager as session_manager
from tools.unified_tools import ToolExecutor
from agents.unified_planning_agent import UnifiedPlanningAgent
from config import FASTAPI_HOST, FASTAPI_PORT

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 建立 FastAPI 應用
app = FastAPI(
    title="統一企劃需求助手 API",
    description="整合企劃專案管理和受眾分析的統一服務",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 設定 CORS（支援環境變數白名單；若未提供則允許所有來源，方便 LAN 訪問）

import os

_origins_env = os.getenv("CORS_ORIGINS", "").strip()
_origins_list = [o.strip() for o in _origins_env.split(",") if o.strip()]

_cors_kwargs = {}

# 若未提供 CORS_ORIGINS 或設為 *，採用萬用星號（關閉 credentials）
if not _origins_list or _origins_env == "*":
    _cors_kwargs = {"allow_origins": ["*"], "allow_credentials": False}
else:
    # 有白名單時，精確匹配並允許帶憑證
    _cors_kwargs = {"allow_origins": _origins_list, "allow_credentials": True}

app.add_middleware(
    CORSMiddleware,
    **_cors_kwargs,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 備援：追加簡單的 CORS 標頭處理，確保 LAN 前端可連線
from fastapi import Request, Response


@app.middleware("http")
async def add_basic_cors_headers(request: Request, call_next):
    # 處理預檢請求
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
            "Access-Control-Allow-Headers": request.headers.get(
                "access-control-request-headers", "*"
            ),
            "Access-Control-Max-Age": "86400",
        }
        return Response(status_code=200, headers=headers)

    # 一般請求附帶 CORS 標頭
    response = await call_next(request)
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault(
        "Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS"
    )
    response.headers.setdefault("Access-Control-Allow-Headers", "*")
    return response


# 相容與正式路由前綴（/api 與 /api/v2 指向相同行為）
from fastapi import APIRouter
from api.routes import router as api_router

app.include_router(api_router, prefix="/api")
app.include_router(api_router, prefix="/api/v2")

# 全局服務實例
llm_client: LLMClient = None
tool_executor: ToolExecutor = None
planning_agent: UnifiedPlanningAgent = None


@app.on_event("startup")
async def startup_event():
    """應用啟動事件"""
    global llm_client, tool_executor, planning_agent

    try:
        # 初始化LLM客戶端
        llm_client = LLMClient()
        logger.info("LLM客戶端初始化完成")

        # 會話管理器由單例入口提供（已初始化）
        logger.info("會話管理器已就緒（單例入口）")

        # 初始化工具執行器
        tool_executor = ToolExecutor(llm_client)
        logger.info("工具執行器初始化完成")

        # 初始化企劃代理
        planning_agent = UnifiedPlanningAgent(llm_client, tool_executor)
        logger.info("企劃代理初始化完成")

        logger.info("所有服務初始化完成")

    except Exception as e:
        logger.error(f"服務初始化失敗: {e}")
        raise


@app.get("/")
async def root():
    """根路徑"""
    return {
        "message": "統一企劃需求助手服務",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "chat": "/chat/turn",
    }


@app.get("/frontend_glass.html")
async def serve_glass() -> FileResponse:
    """直接從後端提供 Glass 前端頁面，避免跨網域問題。"""
    return FileResponse("frontend_glass.html", media_type="text/html")


@app.get("/health")
async def health_check():
    """健康檢查（UTC 即時時間戳與簡化欄位）"""
    try:
        from datetime import timezone

        ts = datetime.now(timezone.utc).isoformat()
        llm_reachable = getattr(llm_client, "healthy", False)
        model_name = getattr(llm_client, "model", None)

        # 仍保留詳細資訊於擴展欄位，方便除錯
        details = {}
        try:
            details["llm_service"] = (
                await llm_client.health_check()
                if llm_client
                else {"status": "not_initialized"}
            )
        except Exception:
            details["llm_service"] = {"status": "error"}

        try:
            details["session_service"] = session_manager.get_session_statistics()
        except Exception:
            details["session_service"] = {"status": "error"}

        return {
            "status": "ok",
            "ts": ts,
            "llm_reachable": llm_reachable,
            "model": model_name,
            **details,
        }
    except Exception as e:
        logger.error(f"健康檢查失敗: {e}")
        from datetime import timezone as _tz

        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "ts": datetime.now(_tz.utc).isoformat(),
            },
        )


@app.get("/models")
async def get_models():
    """獲取可用模型列表"""
    try:
        if llm_client:
            models = llm_client.get_available_models()
            return {"models": models, "current_model": llm_client.model}
        else:
            raise HTTPException(status_code=503, detail="LLM服務未初始化")
    except Exception as e:
        logger.error(f"獲取模型列表失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====== Brief v1.1 兼容資料結構與工具 ======

# Brief 合約中的 slot 名稱集合
BRIEF_SLOT_NAMES = {
    "industry",
    "objective",
    "campaign_theme",
    "proposal_due_date",
    "campaign_period",
    "total_budget",
    "media_formats",
    "plan_type",
    "audience_targeting",
    "audience_behavior",
    "client_assets",
    "client_requirements",
    "tech_requirements",
    "risks",
    "next_steps",
}

# 欄位引導順序（固定）
SLOT_ORDER = [
    "industry",
    "objective",
    "audience_targeting",
    "campaign_theme",
    "campaign_period",
    "proposal_due_date",
    "total_budget",
    "media_formats",
    "plan_type",
    "audience_behavior",
    "client_assets",
    "client_requirements",
    "tech_requirements",
    "risks",
    "next_steps",
]


class ChatAPIMessage(BaseModel):
    role: str
    content: str


class ChatAPIRequest(BaseModel):
    messages: List[ChatAPIMessage]
    slots: Optional[Dict[str, Any]] = None
    history_limit: Optional[int] = 8


class SuggestionItem(BaseModel):
    label: str
    slot: str
    value: str
    send_as_user: str


class ChatAPIResponse(BaseModel):
    next_question: str
    message: Optional[str] = ""
    suggestions: List[SuggestionItem]
    slot_writes: Dict[str, Any]
    rationale_cards: List[Dict[str, Any]] = Field(default_factory=list)
    preview_blocks: List[Dict[str, str]]
    completion: int


def _clamp_text(text: str, limit: int = 100) -> str:
    if not isinstance(text, str):
        return ""
    s = " ".join(text.split())
    return s if len(s) <= limit else s[:limit]


def _brief_slots_from_project(project: ProjectData) -> Dict[str, Any]:
    """將 ProjectData 轉成 brief 合約的 slots 形狀。"""
    campaign_period = {
        "start": project.time_budget.campaign_start_date,
        "end": project.time_budget.campaign_end_date,
    }
    # audience_targeting 以 audience_lock 為主（單值退化）；若有行為分析，保留為 audience_behavior
    audience_targeting = (
        [project.content_strategy.audience_lock]
        if project.content_strategy.audience_lock
        else []
    )

    media_formats = project.content_strategy.media_formats or []
    if isinstance(media_formats, str):
        media_formats = [media_formats]

    plan_types = project.content_strategy.planning_types or []
    plan_type = plan_types[0] if isinstance(plan_types, list) and plan_types else None

    # 現有模型未包含 risks/next_steps/client_assets/requirements 的 array 形態，這裡先做基本映射
    client_assets = (
        [project.content_strategy.client_materials]
        if project.content_strategy.client_materials
        else []
    )
    client_requirements = (
        [project.content_strategy.client_requests]
        if project.content_strategy.client_requests
        else []
    )

    return {
        "industry": project.project_attributes.industry,
        "objective": project.project_attributes.description
        or project.project_attributes.objective,
        "campaign_theme": project.project_attributes.campaign,
        "proposal_due_date": project.time_budget.planning_due_date,
        "campaign_period": campaign_period,
        "total_budget": project.time_budget.budget,
        "media_formats": media_formats,
        "plan_type": plan_type,
        "audience_targeting": audience_targeting,
        "audience_behavior": project.content_strategy.audience_behavior,
        "client_assets": client_assets,
        "client_requirements": client_requirements,
        # 無對應欄位，保留為空陣列以符合合約
        "tech_requirements": (
            [project.technical_needs.technical_needs]
            if project.technical_needs.technical_needs
            else []
        ),
        "risks": [],
        "next_steps": [],
    }


def _update_project_from_brief_slots(
    project: ProjectData, slots: Optional[Dict[str, Any]]
) -> None:
    if not slots:
        return
    # project_attributes
    if "industry" in slots:
        project.project_attributes.industry = slots.get("industry")
    if "objective" in slots:
        project.project_attributes.objective = slots.get("objective")
    if "campaign_theme" in slots:
        project.project_attributes.campaign = slots.get("campaign_theme")

    # time_budget
    if "proposal_due_date" in slots:
        project.time_budget.planning_due_date = slots.get("proposal_due_date")
    if "campaign_period" in slots and isinstance(slots["campaign_period"], dict):
        cp = slots["campaign_period"]
        project.time_budget.campaign_start_date = cp.get("start")
        project.time_budget.campaign_end_date = cp.get("end")
    if "total_budget" in slots:
        project.time_budget.budget = slots.get("total_budget")

    # content_strategy
    if "media_formats" in slots:
        mf = slots.get("media_formats")
        if isinstance(mf, list):
            project.content_strategy.media_formats = mf
        elif isinstance(mf, str):
            project.content_strategy.media_formats = [mf]
    if "plan_type" in slots:
        pt = slots.get("plan_type")
        project.content_strategy.planning_types = [pt] if pt else []
    if "audience_targeting" in slots:
        at = slots.get("audience_targeting")
        if isinstance(at, list) and at:
            project.content_strategy.audience_lock = at[0]
    if "audience_behavior" in slots:
        project.content_strategy.audience_behavior = slots.get("audience_behavior")
    if "client_assets" in slots:
        ca = slots.get("client_assets")
        if isinstance(ca, list):
            project.content_strategy.client_materials = ", ".join(
                [str(x) for x in ca if x]
            )
        elif isinstance(ca, str):
            project.content_strategy.client_materials = ca
    if "client_requirements" in slots:
        cr = slots.get("client_requirements")
        if isinstance(cr, list):
            project.content_strategy.client_requests = ", ".join(
                [str(x) for x in cr if x]
            )
        elif isinstance(cr, str):
            project.content_strategy.client_requests = cr

    # technical_needs（合約是陣列，模型為單字串，先合併為一行）
    if "tech_requirements" in slots:
        tr = slots.get("tech_requirements")
        if isinstance(tr, list):
            project.technical_needs.technical_needs = ", ".join(
                [str(x) for x in tr if x]
            )
        elif isinstance(tr, str):
            project.technical_needs.technical_needs = tr


def _is_filled_slot(slot_key: str, slots: Dict[str, Any]) -> bool:
    """嚴格填寫規則檢查（以 slots 為唯一真相）。"""
    value = slots.get(slot_key)
    if slot_key == "industry":
        return isinstance(value, str) and value.strip() != ""
    if slot_key == "campaign_theme":
        return isinstance(value, str) and value.strip() != ""
    if slot_key == "objective":
        return isinstance(value, str) and value.strip() != ""
    if slot_key == "proposal_due_date":
        return isinstance(value, str) and value.strip() != ""
    if slot_key == "campaign_period":
        return isinstance(value, dict) and ((value.get("start") and value.get("end")))
    if slot_key == "total_budget":
        # 至少包含正整數數字
        if isinstance(value, (int, float)):
            return value > 0
        if isinstance(value, str):
            m = re.search(r"\d+", value)
            return bool(m) and int(m.group(0)) > 0
        return False
    if slot_key == "media_formats":
        return isinstance(value, list) and len(value) > 0
    if slot_key == "plan_type":
        return isinstance(value, str) and value.strip() != ""
    if slot_key == "audience_targeting":
        return isinstance(value, list) and len(value) > 0
    if slot_key == "audience_behavior":
        return isinstance(value, str) and value.strip() != ""
    if slot_key in (
        "client_assets",
        "client_requirements",
        "tech_requirements",
        "risks",
        "next_steps",
    ):
        return isinstance(value, list) and len(value) > 0
    return False


def _compute_weighted_completion(slots: Dict[str, Any]) -> int:
    score = 0
    if _is_filled_slot("industry", slots):
        score += 10
    if _is_filled_slot("campaign_theme", slots):
        score += 15
    if _is_filled_slot("proposal_due_date", slots):
        score += 5
    if _is_filled_slot("campaign_period", slots):
        score += 10
    if _is_filled_slot("total_budget", slots):
        score += 10
    if _is_filled_slot("media_formats", slots):
        score += 10
    if _is_filled_slot("plan_type", slots):
        score += 10
    if _is_filled_slot("audience_targeting", slots):
        score += 15
    if _is_filled_slot("audience_behavior", slots):
        score += 5
    if _is_filled_slot("client_assets", slots):
        score += 2
    if _is_filled_slot("client_requirements", slots):
        score += 3
    if _is_filled_slot("tech_requirements", slots):
        score += 3
    if _is_filled_slot("risks", slots):
        score += 1
    if _is_filled_slot("next_steps", slots):
        score += 1
    return min(score, 100)


def _internal_missing_to_brief_slot(internal_key: str) -> Optional[str]:
    mapping = {
        "project_attributes.industry": "industry",
        "project_attributes.campaign": "campaign_theme",
        "time_budget.planning_due_date": "proposal_due_date",
        "time_budget.campaign_start_date": "campaign_period",
        "time_budget.campaign_end_date": "campaign_period",
        "time_budget.budget": "total_budget",
        "content_strategy.media_formats": "media_formats",
        "content_strategy.planning_types": "plan_type",
        "content_strategy.audience_lock": "audience_targeting",
        "content_strategy.audience_behavior": "audience_behavior",
        "content_strategy.client_materials": "client_assets",
        "content_strategy.client_requests": "client_requirements",
        "technical_needs.technical_needs": "tech_requirements",
    }
    return mapping.get(internal_key)


def _default_suggestions_for_slot(
    slot: str, context_slots: Optional[Dict[str, Any]] = None
) -> List[str]:
    """根據目前 slots 狀態，動態產生更貼近情境的建議候選。"""
    ctx = context_slots or {}
    industry = (
        (ctx.get("industry") or "").lower()
        if isinstance(ctx.get("industry"), str)
        else ""
    )
    objective = (
        (ctx.get("objective") or "") if isinstance(ctx.get("objective"), str) else ""
    )
    media = ctx.get("media_formats") or []

    if slot == "industry":
        return ["科技產品", "消費品", "服務業", "教育單位", "金融服務"]

    if slot == "campaign_theme":
        if any(k in industry for k in ["zoo", "動物", "動物園"]):
            return [
                "家庭日｜動物互動體驗",
                "校園合作｜生命教育週",
                "內容共創｜打卡照片募集",
                "會員回流｜限定夜間場",
            ]
        if "科" in objective or "科技" in industry:
            return ["新品體驗檔", "技術亮點故事", "KOL 開箱評測", "企業案例集"]
        if "品牌" in objective:
            return ["品牌故事檔", "口碑增長檔", "形象影片檔", "社群共創檔"]
        return ["體驗活動", "KOL 串聯", "內容共創", "檔期導購"]

    if slot == "proposal_due_date":
        return ["本週五", "下週三", "兩週內", "月底前"]

    if slot == "campaign_period":
        # 若已有 due_date，給出兩種長短期建議
        return ["下月初到月底", "Q4 整季", "兩週試跑", "三個月整體檔期"]

    if slot == "total_budget":
        # 依已選媒體粗估級距
        base = ["50萬", "100萬", "300萬", "500萬"]
        if isinstance(media, list) and len(media) >= 3:
            return ["300萬", "500萬", "1000萬"]
        if "影音" in media or "OTT" in ",".join(media):
            return ["100萬", "300萬", "500萬"]
        if "搜尋" in media:
            return ["50萬", "100萬", "300萬"]
        return base

    if slot == "media_formats":
        if "科技" in industry:
            return ["搜尋", "社群", "內容行銷", "影音"]
        if any(k in industry for k in ["美妝", "消費"]):
            return ["社群", "影音", "影響者", "口碑/論壇"]
        if any(k in industry for k in ["餐", "食品", "餐飲"]):
            return ["社群", "OOH", "短影音", "部落客/口碑"]
        return ["社群", "搜尋", "OOH", "影音", "內容行銷"]

    if slot == "plan_type":
        if "品牌" in objective:
            return ["策略提案", "品牌故事架構", "形象影片腳本"]
        if any(k in objective for k in ["名單", "轉換", "收單"]):
            return ["成效導向規劃", "漏斗頁面內容", "素材測試計畫"]
        return ["策略提案", "創意版位", "文案", "市場分析"]

    if slot == "audience_targeting":
        return ["家庭親子", "年輕族群", "教育單位", "企業決策者"]

    if slot == "audience_behavior":
        if "科技" in industry:
            return ["常用 YouTube/搜尋", "偏好長文評測", "重視規格與價格"]
        if any(k in industry for k in ["美妝", "消費"]):
            return ["常用 IG/小紅書", "喜歡開箱與教學", "重口碑比較"]
        return ["常用 IG/YouTube", "偏好長文評測", "喜歡短影音", "價格敏感"]

    if slot == "tech_requirements":
        return ["像素追蹤", "GA4 設置", "CRM 整合", "轉換 API"]

    return ["提供更多資訊", "需要進一步具體化", "先給方向"]


def _make_chips(slot: str, labels: List[str]) -> List[SuggestionItem]:
    chips: List[SuggestionItem] = []
    for label in labels:
        chips.append(
            SuggestionItem(
                label=label,
                slot=slot,
                value=label,
                send_as_user=label,
            )
        )
    return chips


def _get_audience_chips(industry: Optional[str]) -> List[SuggestionItem]:
    ind = (industry or "").lower()
    generic = ["一般消費者", "企業決策者", "教育單位", "政府單位", "合作夥伴"]
    zoo = ["家庭親子客", "校園團體", "情侶/年輕族群", "旅遊客", "企業包場/贈票"]
    finance = ["B2C 個人金融", "B2B 企業金融", "財富管理", "保險"]
    saas = ["SMB", "Enterprise", "開發者", "行銷團隊"]
    fnb = ["上班族午晚餐", "家庭客", "觀光客", "外送客"]

    labels: List[str]
    if "zoo" in ind or "動物" in ind or "動物園" in ind:
        labels = zoo
    elif "fin" in ind or "金融" in ind:
        labels = finance
    elif "saas" in ind or "軟體" in ind or "雲" in ind:
        labels = saas
    elif "餐" in ind or "餐飲" in ind or "food" in ind:
        labels = fnb
    else:
        labels = generic

    chips = _make_chips("audience_targeting", labels[:5])
    # 永遠保留一顆「我再想想」
    chips.append(
        SuggestionItem(
            label="我再想想",
            slot="audience_targeting",
            value="",
            send_as_user="我再想想",
        )
    )
    return chips


def _get_opening_text(industry: Optional[str], theme: Optional[str] = None) -> str:
    ind = industry or ""
    if any(k in ind for k in ["動物", "動物園", "zoo", "ZOO"]):
        tn = (theme or "").strip()
        lead = f"已了解您要推廣{tn}，" if tn else "已了解您的推廣需求，"
        text = (
            lead
            + "動物園常見的溝通主軸是『寓教於樂、稀有體驗、拍照分享』。"
            + "請問這檔期主要想觸達哪些族群？（例如：家庭親子、校園團體、情侶年輕族群、旅遊客）"
        )
        return _clamp_text(text)
    if "金融" in ind or "finance" in ind.lower():
        text = (
            "金融行銷的關鍵在『建立信任、合規清楚、把複雜說簡單』。"
            "這檔期主要對誰說話？"
        )
        return _clamp_text(text)
    return _clamp_text("這檔期主要對誰說話？")


def _build_rationale_for_theme(
    industry: Optional[str], audience: Optional[str], theme: Optional[str]
) -> List[Dict[str, Any]]:
    """產生主題理由卡（2–4 點），覆蓋：受眾匹配 / 場景或洞察 / 可落地點。
    嚴禁硬編數據，使用通用可落地描述。"""
    bullets: List[str] = []
    aud = audience or "目標受眾"

    # 受眾匹配
    bullets.append(f"受眾匹配：{aud}的常見動機與需求與此主題契合，溝通更聚焦且易轉化。")
    # 場景或洞察
    if industry and (
        "動物" in industry or "動物園" in industry or industry.lower().find("zoo") >= 0
    ):
        bullets.append(
            "記憶點：現場互動、餵食與合照是天然內容來源，容易形成到此一遊畫面。"
        )
    elif industry and (
        "食品" in industry or "餐" in industry or "food" in industry.lower()
    ):
        bullets.append(
            "場景精準：用餐高峰可放大觸達，搭配快取或健康訴求易被理解與採納。"
        )
    else:
        bullets.append("情境抓手：結合使用情境與明確利益點，讓主題更容易被記住與分享。")
    # 可落地點
    bullets.append(
        "可落地：以既有資源組合『檔期活動＋內容素材＋合作位』，即可快速上線驗證。"
    )

    return [{"title": "為何這個主題", "bullets": bullets[:4]}]


def _parse_zh_duration(text: str) -> Optional[Dict[str, int]]:
    mapping = {
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    m = re.search(r"([一二三四五六七八九]|\d+)(個)?月", text)
    if m:
        val = mapping.get(m.group(1)) if m.group(1) in mapping else None
        if val is None:
            try:
                val = int(m.group(1))
            except Exception:
                val = None
        if val:
            return {"months": val}
    w = re.search(r"([一二三四五六七八九]|\d+)(個)?週", text)
    if w:
        val = mapping.get(w.group(1)) if w.group(1) in mapping else None
        if val is None:
            try:
                val = int(w.group(1))
            except Exception:
                val = None
        if val:
            return {"weeks": val}
    return None


def _date_from_choice(choice: str) -> Optional[str]:
    today = datetime.now()
    c = choice or ""
    if "下月初" in c:
        year = today.year + 1 if today.month == 12 else today.year
        month = 1 if today.month == 12 else today.month + 1
        start = datetime(year, month, 1)
        return start.strftime("%Y-%m-%d")
    if "下週一" in c or "下周一" in c:
        days_ahead = (7 - today.weekday()) % 7
        days_ahead = 7 if days_ahead == 0 else days_ahead
        start = today + timedelta(days=days_ahead)
        return start.strftime("%Y-%m-%d")
    m = re.search(r"\d{4}-\d{1,2}-\d{1,2}", c)
    if m:
        try:
            dt = datetime.strptime(m.group(0), "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None
    return None


def _add_duration(start_str: str, hint: Dict[str, int]) -> Optional[str]:
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        if hint.get("months"):
            months = hint["months"]
            year = start.year
            month = start.month + months
            year += (month - 1) // 12
            month = ((month - 1) % 12) + 1
            next_start = datetime(year, month, 1)
            end = next_start - timedelta(days=1)
            return end.strftime("%Y-%m-%d")
        if hint.get("weeks"):
            end = start + timedelta(weeks=hint["weeks"]) - timedelta(days=1)
            return end.strftime("%Y-%m-%d")
    except Exception:
        return None
    return None


def _build_preview_blocks(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    title_map = {
        "industry": "產業",
        "campaign_theme": "活動主題",
        "proposal_due_date": "提案交付日期",
        "campaign_period": "活動期間",
        "total_budget": "專案總預算",
        "media_formats": "投放形式",
        "plan_type": "企劃類型",
        "audience_targeting": "受眾鎖定",
        "audience_behavior": "受眾行為分析",
        "client_assets": "客戶素材",
        "client_requirements": "客戶要求",
        "tech_requirements": "技術需求",
        "risks": "風險評估",
        "next_steps": "後續步驟",
    }

    blocks: List[Dict[str, str]] = []
    for key in [
        "industry",
        "campaign_theme",
        "proposal_due_date",
        "campaign_period",
        "total_budget",
        "media_formats",
        "plan_type",
        "audience_targeting",
        "audience_behavior",
        "client_assets",
        "client_requirements",
        "tech_requirements",
        "risks",
        "next_steps",
    ]:
        value = slots.get(key)
        if key == "campaign_period" and isinstance(value, dict):
            content = f"{value.get('start') or '-'} 至 " f"{value.get('end') or '-'}"
        elif isinstance(value, list):
            content = ", ".join([str(x) for x in value if x]) if value else "未填"
        else:
            content = value or "未填"
        blocks.append(
            {
                "id": key,
                "title": title_map.get(key, key),
                "content": str(content),
            }
        )
    return blocks


def _apply_quick_intent_from_text(project: ProjectData, text: str) -> None:
    """根據短字串快速寫入常見槽位（解決使用者純文字輸入時無法被工具提取的狀況）。"""
    if not text:
        return
    t = text.strip()
    # 目標（objective）常見詞
    objective_labels = {"品牌知名度", "帶動試用", "名單收集", "促銷轉換"}
    if t in objective_labels:
        project.project_attributes.objective = t
        return
    # 受眾鎖定（簡單匹配）
    audience_labels = {"家庭親子", "年輕族群", "教育單位", "企業決策者"}
    if t in audience_labels:
        # 與 brief 契約一致：audience_lock 單值
        project.content_strategy.audience_lock = t
        return


def _diff_slot_writes(
    before_slots: Dict[str, Any], after_slots: Dict[str, Any]
) -> Dict[str, Any]:
    writes: Dict[str, Any] = {}
    for key in BRIEF_SLOT_NAMES:
        if key not in after_slots:
            continue
        b = before_slots.get(key)
        a = after_slots.get(key)
        if b != a and a not in (None, "", [], {}):
            writes[key] = a
    return writes


def _make_next_question(focus_slot: Optional[str]) -> str:
    mapping = {
        "industry": "請問您的產業類別是？",
        "campaign_theme": "這次活動的主題是什麼？",
        "proposal_due_date": "提案希望哪天交付？",
        "campaign_period": "活動預計從何時到何時？",
        "total_budget": "總預算大約多少？",
        "media_formats": "打算採用哪些投放形式？",
        "plan_type": "本次企劃類型傾向是？",
        "audience_targeting": "目標受眾是哪些族群？",
        "audience_behavior": "受眾有哪些明顯行為特徵？",
        "client_assets": "目前有哪些可用素材？",
        "client_requirements": "客戶是否有特別要求？",
        "tech_requirements": "是否有技術或整合上的需求？",
        "risks": "有評估過的風險點嗎？",
        "next_steps": "下一步想怎麼推進？",
    }
    return mapping.get(focus_slot, "可以再多描述一點專案重點嗎？")


@app.post("/chat/turn", response_model=ChatTurnResponse)
async def chat_turn(request: ChatTurnRequest):
    """統一的聊天回合端點"""
    try:
        if not planning_agent:
            raise HTTPException(status_code=503, detail="企劃代理未初始化")

        # 獲取或創建會話
        session_data = session_manager.get_session(request.session_id)
        if not session_data:
            # 創建新會話
            session_data = session_manager.create_session()
            request.session_id = session_data.session_id

        # 獲取現有專案數據
        project_data = session_data.project_data

        # 處理聊天回合
        response = await planning_agent.process_chat_turn(
            user_message=request.message,
            session_id=request.session_id,
            project_data=project_data,
        )

        # 更新會話
        session_manager.update_session(
            request.session_id, project_data=response.project_data
        )

        return response

    except Exception as e:
        logger.error(f"處理聊天回合失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat", response_model=ChatAPIResponse)
async def chat_api(
    request: ChatAPIRequest,
    session_id: Optional[str] = None,
    x_session_id: Optional[str] = Header(None),
):
    """Brief v1.1 合約的對話端點包裝器。"""
    try:
        if not tool_executor:
            raise HTTPException(status_code=503, detail="工具執行器未初始化")

        # 1) 準備初始專案資料（由 slots 映射）
        project = ProjectData()
        before_slots = _brief_slots_from_project(project)
        if request.slots:
            _update_project_from_brief_slots(project, request.slots)
            before_slots = _brief_slots_from_project(project)

        # 2) 取最後一則 user 訊息
        user_msg = ""
        for m in reversed(request.messages or []):
            if (m.role or "").lower() == "user":
                user_msg = m.content or ""
                break

        # 2.1) 嘗試綁定會話（支援 query 參數或 X-Session-Id 標頭）
        sid = x_session_id or session_id
        if sid:
            # 確保會話存在
            sess = session_manager.get_session(sid)
            if not sess:
                # 若不存在則創建（不指定 user_id）
                new_sess = session_manager.create_session()
                sid = new_sess.session_id
            # 寫入用戶訊息
            if user_msg.strip():
                session_manager.add_chat_message(sid, MessageRole.USER, user_msg)

        # 3) 透過工具嘗試從 user 輸入提取結構化資料並更新 ProjectData；若沒有命中則套用 quick intent
        if user_msg.strip():
            result = await tool_executor.execute_tool(
                "extract_project_data", user_message=user_msg
            )
            extracted_any = False
            if result.success and isinstance(result.data, dict):
                # 以 UnifiedAgent 的更新邏輯一致地寫回
                for section, section_data in result.data.items():
                    if hasattr(project, section) and isinstance(section_data, dict):
                        section_obj = getattr(project, section)
                        for key, value in section_data.items():
                            if hasattr(section_obj, key) and value is not None:
                                setattr(section_obj, key, value)
                                extracted_any = True
            if not extracted_any:
                _apply_quick_intent_from_text(project, user_msg)

        # 4) 生成回傳所需的 brief slots
        after_slots = _brief_slots_from_project(project)

        # 5) 僅以 slots 為準計算完成度與缺失欄位（固定順序）
        completion = _compute_weighted_completion(after_slots)
        missing_brief: List[str] = [
            key for key in SLOT_ORDER if not _is_filled_slot(key, after_slots)
        ]

        # 依情境微調優先詢問的槽位（例如動物園先問受眾）
        def _select_focus_slot(
            missing: List[str], slots: Dict[str, Any], last_text: str
        ) -> Optional[str]:
            if not missing:
                return None
            ind = slots.get("industry") or ""
            theme = slots.get("campaign_theme") or ""
            text = last_text or ""
            zoo_hit = any(
                k in (ind + theme + text) for k in ["動物", "動物園", "zoo", "長頸鹿"]
            )
            if zoo_hit and "audience_targeting" in missing:
                return "audience_targeting"
            return missing[0]

        focus_slot = _select_focus_slot(missing_brief, after_slots, user_msg)

        # 建議泡泡（3-5則）與下一題
        msg_text = ""
        if focus_slot == "objective":
            # 目標 chips（簡易通用）
            labels = ["品牌知名度", "帶動試用", "名單收集", "促銷轉換"]
            suggestions = _make_chips("objective", labels)
            next_q = _clamp_text("請問這次企劃的主要目標是什麼？")
            msg_text = next_q
        elif focus_slot == "audience_targeting":
            suggestions = _get_audience_chips(after_slots.get("industry"))
            next_q = _clamp_text(
                _get_opening_text(
                    after_slots.get("industry"), after_slots.get("campaign_theme")
                )
            )
            msg_text = next_q
        else:
            raw_sugs = (
                _default_suggestions_for_slot(focus_slot, after_slots)
                if focus_slot
                else []
            )
            suggestions = [
                SuggestionItem(
                    label=s,
                    slot=focus_slot or "industry",
                    value=s,
                    send_as_user=s,
                )
                for s in raw_sugs[:5]
            ] or [
                SuggestionItem(
                    label="提供更多資訊",
                    slot=focus_slot or "industry",
                    value="提供更多資訊",
                    send_as_user="提供更多資訊",
                )
            ]
            next_q = _clamp_text(_make_next_question(focus_slot))
            msg_text = next_q

        # 下一個問題（已於上方決定並做 100 字裁切）

        # slot_writes 僅輸出有變更者
        slot_writes = _diff_slot_writes(before_slots, after_slots)

        # 預覽區塊
        preview_blocks = _build_preview_blocks(after_slots)

        # 若本輪寫入了 campaign_theme，補理由卡
        rationale_cards: List[Dict[str, Any]] = []
        if slot_writes.get("campaign_theme"):
            rationale_cards = _build_rationale_for_theme(
                after_slots.get("industry"),
                (after_slots.get("audience_targeting") or [None])[0],
                slot_writes.get("campaign_theme"),
            )

        resp = ChatAPIResponse(
            next_question=next_q,
            message=msg_text,
            suggestions=suggestions,
            slot_writes=slot_writes,
            rationale_cards=rationale_cards,
            preview_blocks=preview_blocks,
            completion=completion,
        )

        # 9) 如果綁定到會話，寫回助手訊息，確保之後切回 /chat/turn 能延續
        if sid:
            assistant_text = msg_text or next_q or ""
            if assistant_text:
                session_manager.add_chat_message(
                    sid, MessageRole.ASSISTANT, assistant_text
                )

        return resp
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"/api/chat 處理失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ReportRequest(BaseModel):
    slots: Dict[str, Any]
    preview: Optional[List[Dict[str, Any]]] = None


class ReportResponse(BaseModel):
    brief_markdown: str
    full_markdown: str
    json: Dict[str, Any]


def _generate_brief_markdown(slots: Dict[str, Any]) -> str:
    lines = [
        "## 📋 專案概覽",
        f"**活動名稱**: {slots.get('campaign_theme') or ''}",
        f"**產業類別**: {slots.get('industry') or ''}",
        "",
        "## ⏰ 時程與預算",
        f"**提案交付日期**: {slots.get('proposal_due_date') or ''}",
        f"**活動開始日期**: "
        f"{(slots.get('campaign_period') or {}).get('start') or ''}",
        f"**活動結束日期**: "
        f"{(slots.get('campaign_period') or {}).get('end') or ''}",
        f"**專案總預算**: {slots.get('total_budget') or ''}",
        "",
        "## 🎯 內容與策略",
        f"**企劃類型**: {slots.get('plan_type') or ''}  ",
        f"**投放形式**: {', '.join(slots.get('media_formats') or [])}",
        f"**目標受眾**: {', '.join(slots.get('audience_targeting') or [])}",
        f"**受眾行為分析**: {slots.get('audience_behavior') or ''}",
        "",
        "## 📦 客戶資源",
        f"**客戶素材**: {', '.join(slots.get('client_assets') or [])}",
        f"**客戶要求**: {', '.join(slots.get('client_requirements') or [])}",
        "",
        "## 🔧 技術需求",
        f"{', '.join(slots.get('tech_requirements') or [])}",
    ]
    return "\n".join(lines).strip()


def _generate_full_markdown(slots: Dict[str, Any]) -> str:
    campaign_period = slots.get("campaign_period") or {}
    return (
        "## 📋 專案概覽\n"
        f"**活動名稱**: {slots.get('campaign_theme') or ''}\n"
        f"**產業類別**: {slots.get('industry') or ''}\n"
        f"**緊急程度**: {'急案' if False else '一般案件'}\n\n"
        "## ⏰ 時程與預算\n"
        f"**提案交付日期**: {slots.get('proposal_due_date') or ''}\n"
        f"**活動開始日期**: {campaign_period.get('start') or ''}\n"
        f"**活動結束日期**: {campaign_period.get('end') or ''}\n"
        f"**專案總預算**: {slots.get('total_budget') or ''}\n\n"
        "## 🎯 內容與策略\n"
        f"**企劃類型**: {slots.get('plan_type') or ''}  "
        f"**投放形式**: {', '.join(slots.get('media_formats') or [])}\n"
        f"**目標受眾**: {', '.join(slots.get('audience_targeting') or [])}\n"
        f"**受眾行為分析**: {slots.get('audience_behavior') or ''}\n\n"
        "## 📦 客戶資源\n"
        f"**客戶素材**: {', '.join(slots.get('client_assets') or [])}\n"
        f"**客戶要求**: {', '.join(slots.get('client_requirements') or [])}\n\n"
        "## 🔧 技術需求\n\n"
        "## 📊 提案內容\n\n"
        "### 市場洞察\n\n"
        "### 競品分析\n\n"
        "### 策略提案\n\n"
        "### 媒體規劃\n\n"
        "### 預算及預估成效\n\n"
        "### 時程規劃\n\n"
        "### 技術需求\n\n"
        "### 風險評估\n\n"
        "### 後續步驟\n"
    ).strip()


@app.post("/api/report", response_model=ReportResponse)
async def report_api(request: ReportRequest):
    """Brief v1.1 合約的報告端點。"""
    try:
        slots = request.slots or {}
        # 重新計算完成度（若需要可返回到 json 中）
        completion = _compute_weighted_completion(slots)
        brief_md = _generate_brief_markdown(slots)
        full_md = _generate_full_markdown(slots)
        payload = {"slots": slots, "outline": {}, "completion": completion}
        return ReportResponse(
            brief_markdown=brief_md,
            full_markdown=full_md,
            json=payload,
        )
    except Exception as e:
        logger.error(f"/api/report 生成失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/sessions")
async def list_sessions(user_id: str = None):
    """列出會話"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        sessions = session_manager.list_sessions(user_id)
        return {"sessions": sessions, "total": len(sessions)}
    except Exception as e:
        logger.error(f"列出會話失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/sessions/{session_id}")
async def get_session(session_id: str):
    """獲取會話詳情"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="會話不存在")

        return {
            "session_id": session_data.session_id,
            "user_id": session_data.user_id,
            "project_data": session_data.project_data,
            "chat_history": session_data.chat_history,
            "created_at": session_data.created_at.isoformat(),
            "updated_at": session_data.updated_at.isoformat(),
            "status": session_data.status,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取會話詳情失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """刪除會話"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        success = session_manager.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="會話不存在或刪除失敗")

        return {"message": "會話刪除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除會話失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/sessions/{session_id}/close")
async def close_session(session_id: str):
    """關閉會話"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        success = session_manager.close_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="會話不存在或關閉失敗")

        return {"message": "會話關閉成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"關閉會話失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/sessions/{session_id}/project")
async def get_project_data(session_id: str):
    """獲取專案數據"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        project_data = session_manager.get_project_data(session_id)
        if not project_data:
            raise HTTPException(status_code=404, detail="專案數據不存在")

        return project_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取專案數據失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/chat/sessions/{session_id}/project")
async def update_project_data(session_id: str, project_data: ProjectData):
    """更新專案數據"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        success = session_manager.update_project_data(session_id, project_data)
        if not success:
            raise HTTPException(status_code=404, detail="會話不存在或更新失敗")

        return {"message": "專案數據更新成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新專案數據失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/sessions/{session_id}/history")
async def get_chat_history(session_id: str):
    """獲取聊天歷史"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        chat_history = session_manager.get_chat_history(session_id)
        return {
            "session_id": session_id,
            "chat_history": chat_history,
            "total_messages": len(chat_history),
        }
    except Exception as e:
        logger.error(f"獲取聊天歷史失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/sessions/{session_id}/reset")
async def reset_session(session_id: str):
    """重置會話"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        # 獲取會話
        session_data = session_manager.get_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="會話不存在")

        # 重置專案數據和聊天歷史
        session_data.project_data = ProjectData()
        session_data.chat_history = []
        session_data.status = "active"

        # 更新會話
        success = session_manager.update_session(session_id, session_data)
        if not success:
            raise HTTPException(status_code=500, detail="重置會話失敗")

        return {"message": "會話重置成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置會話失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_statistics():
    """獲取統計資訊"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        stats = session_manager.get_session_statistics()
        return stats
    except Exception as e:
        logger.error(f"獲取統計資訊失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cleanup")
async def cleanup_old_sessions(days: int = 30):
    """清理舊會話"""
    try:
        if not session_manager:
            raise HTTPException(status_code=503, detail="會話管理器未初始化")

        cleanup_count = session_manager.cleanup_old_sessions(days)
        return {
            "message": f"清理完成，共刪除 {cleanup_count} 個舊會話",
            "cleanup_count": cleanup_count,
            "days": days,
        }
    except Exception as e:
        logger.error(f"清理舊會話失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 注意：/analyze/ 端點已廢棄，統一使用 /chat/turn =====


# ===== 輔助函數 =====


def calculate_completeness_score(project_data: ProjectData) -> float:
    """計算專案完整度分數"""
    if not project_data:
        return 0.0

    total_fields = 0
    filled_fields = 0

    # 檢查專案屬性
    if project_data.project_attributes:
        attrs = project_data.project_attributes
        total_fields += 4
        if attrs.industry:
            filled_fields += 1
        if attrs.campaign:
            filled_fields += 1
        if attrs.is_urgent is not None:
            filled_fields += 1
        if attrs.description:
            filled_fields += 1

    # 檢查時間預算
    if project_data.time_budget:
        budget = project_data.time_budget
        total_fields += 4
        if budget.planning_due_date:
            filled_fields += 1
        if budget.campaign_start_date:
            filled_fields += 1
        if budget.campaign_end_date:
            filled_fields += 1
        if budget.budget:
            filled_fields += 1

    # 檢查內容策略
    if project_data.content_strategy:
        strategy = project_data.content_strategy
        total_fields += 6
        if strategy.planning_types:
            filled_fields += 1
        if strategy.media_formats:
            filled_fields += 1
        if strategy.audience_lock:
            filled_fields += 1
        if strategy.audience_behavior:
            filled_fields += 1
        if strategy.client_materials:
            filled_fields += 1
        if strategy.client_requests:
            filled_fields += 1

    # 檢查技術需求
    if project_data.technical_needs:
        tech = project_data.technical_needs
        total_fields += 3
        if tech.technical_needs:
            filled_fields += 1
        if tech.platform_requirements:
            filled_fields += 1
        if tech.integration_needs:
            filled_fields += 1

    # 檢查受眾洞察
    if project_data.audience_insights:
        audience = project_data.audience_insights
        total_fields += 6
        if audience.target_demographics:
            filled_fields += 1
        if audience.psychographic_profile:
            filled_fields += 1
        if audience.behavior_patterns:
            filled_fields += 1
        if audience.pain_points:
            filled_fields += 1
        if audience.motivations:
            filled_fields += 1
        if audience.media_preferences:
            filled_fields += 1

    if total_fields == 0:
        return 0.0

    return filled_fields / total_fields


def identify_missing_fields(project_data: ProjectData) -> List[str]:
    """識別缺失的欄位"""
    missing = []

    if not project_data:
        return ["project_data"]

    # 檢查專案屬性
    if project_data.project_attributes:
        attrs = project_data.project_attributes
        if not attrs.industry:
            missing.append("project_attributes.industry")
        if not attrs.campaign:
            missing.append("project_attributes.campaign")
        if attrs.is_urgent is None:
            missing.append("project_attributes.is_urgent")
        if not attrs.description:
            missing.append("project_attributes.description")

    # 檢查時間預算
    if project_data.time_budget:
        budget = project_data.time_budget
        if not budget.planning_due_date:
            missing.append("time_budget.planning_due_date")
        if not budget.campaign_start_date:
            missing.append("time_budget.campaign_start_date")
        if not budget.campaign_end_date:
            missing.append("time_budget.campaign_end_date")
        if not budget.budget:
            missing.append("time_budget.budget")

    # 檢查內容策略
    if project_data.content_strategy:
        strategy = project_data.content_strategy
        if not strategy.planning_types:
            missing.append("content_strategy.planning_types")
        if not strategy.media_formats:
            missing.append("content_strategy.media_formats")
        if not strategy.audience_lock:
            missing.append("content_strategy.audience_lock")
        if not strategy.audience_behavior:
            missing.append("content_strategy.audience_behavior")
        if not strategy.client_materials:
            missing.append("content_strategy.client_materials")
        if not strategy.client_requests:
            missing.append("content_strategy.client_requests")

    # 檢查技術需求
    if project_data.technical_needs:
        tech = project_data.technical_needs
        if not tech.technical_needs:
            missing.append("technical_needs.technical_needs")
        if not tech.platform_requirements:
            missing.append("technical_needs.platform_requirements")
        if not tech.integration_needs:
            missing.append("technical_needs.integration_needs")

    # 檢查受眾洞察
    if project_data.audience_insights:
        audience = project_data.audience_insights
        if not audience.target_demographics:
            missing.append("audience_insights.target_demographics")
        if not audience.psychographic_profile:
            missing.append("audience_insights.psychographic_profile")
        if not audience.behavior_patterns:
            missing.append("audience_insights.behavior_patterns")
        if not audience.pain_points:
            missing.append("audience_insights.pain_points")
        if not audience.motivations:
            missing.append("audience_insights.motivations")
        if not audience.media_preferences:
            missing.append("audience_insights.media_preferences")

    return missing


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app_refactored_unified:app",
        host=FASTAPI_HOST,
        port=FASTAPI_PORT,
        reload=True,
        log_level="info",
    )
