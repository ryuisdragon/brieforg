#!/usr/bin/env python3
"""
DEPRECATED: 此檔案為舊版單體應用入口，僅保留備查。
請改用新入口：`uvicorn app_refactored_unified:app --reload`
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests

from config import (
    OLLAMA_HOST,
    OLLAMA_PORT,
    OLLAMA_DEFAULT_MODEL,
    OLLAMA_TIMEOUT,
    FASTAPI_HOST,
    FASTAPI_PORT,
    COMPLETENESS_THRESHOLD,
    PROJECT_CORE_FIELDS,
    PLANNING_TYPES,
    PROPOSAL_TEMPLATE_FIELDS,
    PREDEFINED_OPTIONS,
    OPTION_SELECTION_RULES,
    QUICK_REPLY_TEMPLATES,
)
from utils import (
    retry_on_failure,
    cache_result,
    monitor_performance,
    handle_ollama_error,
    validate_json_response,
    clean_json_response,
)

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------- 對話式功能常數 ----------
THRESHOLD = 0.85
REQUIRED_FIELDS = [
    "project_attributes.industry",
    "project_attributes.campaign",
    "project_attributes.is_urgent",
    "time_budget.planning_due_date",
    "time_budget.campaign_start_date",
    "time_budget.campaign_end_date",
    "time_budget.budget",
    "content_strategy.planning_types",
    "content_strategy.media_formats",
    "content_strategy.audience_lock",
    "content_strategy.audience_behavior",
    "content_strategy.client_materials",
    "content_strategy.client_requests",
    "technical_needs.technical_needs",
]

FRIENDLY_FIELD_NAMES = {
    "project_attributes.industry": "產業",
    "project_attributes.campaign": "活動主題",
    "project_attributes.is_urgent": "是否急案",
    "time_budget.planning_due_date": "提案交付日期",
    "time_budget.campaign_start_date": "活動開始日期",
    "time_budget.campaign_end_date": "活動結束日期",
    "time_budget.budget": "預算金額",
    "content_strategy.planning_types": "企劃類型",
    "content_strategy.media_formats": "媒體/投放形式",
    "content_strategy.audience_lock": "受眾鎖定",
    "content_strategy.audience_behavior": "受眾行為",
    "content_strategy.client_materials": "客戶素材",
    "content_strategy.client_requests": "客戶要求",
    "technical_needs.technical_needs": "技術需求",
}

# 建立 FastAPI 應用
app = FastAPI(
    title="Ollama FastAPI 後端服務",
    description="提供需求分析和企劃專案需求池功能",
    version="1.0.0",
)

# 設定 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic 模型
class IntakeRequest(BaseModel):
    requirement: str
    user_id: str


class ClarifyRequest(BaseModel):
    original_requirement: str
    clarification_answers: List[str]
    user_id: str


class ProjectIntakeRequest(BaseModel):
    requirement: str
    user_id: str


class ProjectClarifyRequest(BaseModel):
    original_requirement: str
    clarification_answers: List[str]
    user_id: str


# ---------- 對話式功能模型 ----------
class ChatSession(BaseModel):
    session_id: str
    user_id: str
    original_requirement: str
    answers: List[str] = []
    asked_questions: List[str] = []
    last_question: Optional[str] = None
    completeness_score: float = 0.0
    missing_keys: List[str] = []
    has_pending_confirmation: bool = True
    created_at: str = datetime.now().isoformat()
    updated_at: str = datetime.now().isoformat()
    planning_project: Optional[Dict[str, Any]] = None
    proposal_text: Optional[str] = None
    project_data: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    message: str = ""
    user_id: str = "guest"
    session_id: Optional[str] = None


class ChatTurnResponse(BaseModel):
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


class ToolCall(BaseModel):
    function_name: str
    arguments: Dict[str, Any]


class AgentOutput(BaseModel):
    completeness_report: Optional[Dict[str, Any]] = None
    missing_keys: Optional[List[str]] = None
    tool_calls: Optional[List[ToolCall]] = None
    reasoning: Optional[str] = None
    clarification_questions: Optional[List[str]] = None
    proposal_text: Optional[str] = None  # 僅支援字符串格式
    saved_to_chroma: Optional[Dict[str, Any]] = None
    status: Optional[str] = None  # "complete", "need_clarification", "error"
    tool_action: Optional[str] = (
        None  # "ask_clarification", "create_planning_project", "none"
    )
    planning_project: Optional[Dict[str, Any]] = None  # 完整的企劃專案資料


# 子模型定義
from typing import Optional, List

# 重新初始化對話會話存儲
SESSIONS: Dict[str, ChatSession] = {}


class ProjectAttributes(BaseModel):
    industry: Optional[str] = "待確認"
    campaign: Optional[str] = "待確認"
    is_urgent: Optional[bool] = None


class TimeBudget(BaseModel):
    planning_due_date: Optional[str] = None
    campaign_start_date: Optional[str] = None
    campaign_end_date: Optional[str] = None
    budget: Optional[str] = None


class ContentStrategy(BaseModel):
    planning_types: List[str] = []
    media_formats: Optional[str] = None
    audience_lock: Optional[str] = None
    audience_behavior: Optional[str] = None
    client_materials: Optional[str] = None
    client_requests: Optional[str] = None


class TechnicalNeeds(BaseModel):
    technical_needs: Optional[str] = None


class PlanningProject(BaseModel):
    """完整的企劃專案資料模型 (強型別)"""

    project_attributes: ProjectAttributes
    time_budget: TimeBudget
    content_strategy: ContentStrategy
    technical_needs: TechnicalNeeds
    user_id: str
    original_requirement: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ClarificationRequest(BaseModel):
    """澄清問題請求模型"""

    questions: List[str]
    user_id: str
    context: Optional[Dict[str, Any]] = None


class ProposalTemplate(BaseModel):
    """提案模板模型"""

    project_overview: str
    market_analysis: str
    competitive_analysis: str
    strategy_proposal: str
    media_plan: str
    budget_estimation: str
    timeline: str
    technical_requirements: str
    risk_assessment: str
    next_steps: str


class ChromaSaveResult(BaseModel):
    """Chroma 儲存結果模型"""

    success: bool
    document_id: Optional[str] = None
    error_message: Optional[str] = None
    saved_at: Optional[str] = None


# LLM 客戶端
class LLMClient:
    def __init__(self, host: str = OLLAMA_HOST, port: int = OLLAMA_PORT):
        self.base_url = f"http://{host}:{port}"
        self.timeout = OLLAMA_TIMEOUT

    @retry_on_failure()
    def generate_response(self, prompt: str, model: str = None) -> str:
        """生成 LLM 回應"""
        model = model or OLLAMA_DEFAULT_MODEL

        url = f"{self.base_url}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}

        logger.info(f"發送請求到 Ollama: {url}")
        logger.info(f"使用模型: {model}")
        logger.info(f"提示詞長度: {len(prompt)} 字符")

        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()

        result = response.json()
        llm_response = result.get("response", "")

        logger.info(f"Ollama 回應長度: {len(llm_response)} 字符")
        if not llm_response:
            logger.error("Ollama 回應為空")
            raise HTTPException(status_code=500, detail="Ollama 回應為空")

        logger.info(f"Ollama 回應預覽: {llm_response[:200]}...")
        return llm_response

    @cache_result(ttl=300)
    def list_models(self) -> List[str]:
        """獲取可用模型列表"""
        url = f"{self.base_url}/api/tags"
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()

        result = response.json()
        return [model["name"] for model in result.get("models", [])]


# 系統提示詞管理類
class SystemPrompts:
    """統一管理所有系統提示詞 - 專注於企劃專案需求"""

    @staticmethod
    def get_planning_requirement_analysis_prompt() -> str:
        """獲取企劃專案需求分析提示詞"""
        return """你是一個專業的企劃專案需求分析助手。你的任務是分析用戶的企劃需求描述，評估其完整性並返回 JSON 格式的結果。

重要：你必須只返回有效的 JSON 格式，不要包含任何其他文字、解釋或註釋。

請評估以下企劃專案相關方面：
1. 專案屬性是否明確（產業、活動主題、緊急程度）
2. 時間與預算是否清楚（交付日期、活動時程、預算）
3. 內容與策略是否完整（企劃類型、投放形式、受眾定位）
4. 技術需求是否提及
5. 客戶資源是否說明

返回格式：
{
  "completeness_score": 0.85,
  "missing_elements": ["專案預算", "受眾行為分析"],
  "strengths": ["活動主題明確", "時程規劃清楚"],
  "suggestions": ["建議明確預算範圍", "建議補充受眾分析"]
}

記住：只返回 JSON，不要其他內容！"""

    @staticmethod
    def get_planning_clarification_questions_prompt() -> str:
        """獲取企劃專案澄清問題生成提示詞"""
        return """你是一個專業的企劃專案分析助手。基於缺失的企劃專案元素，生成具體的澄清問題。

請生成 3-5 個針對企劃專案的具體問題，幫助用戶補充缺失的企劃需求資訊。
每個問題應該：
1. 針對特定企劃專案缺失元素
2. 具體明確且容易回答
3. 有助於完善企劃專案需求
4. 符合企劃專案的特點

返回格式：
[
  "問題1",
  "問題2", 
  "問題3"
]

記住：只返回 JSON 陣列，不要其他內容！"""

    @staticmethod
    def get_project_extraction_prompt() -> str:
        """獲取企劃專案資料提取提示詞"""
        return """你是一個專業的企劃專案需求分析助手。你的任務是從用戶的企劃需求描述中提取結構化的企劃專案資料。

重要：你必須只返回有效的 JSON 格式，不要包含任何其他文字、解釋或註釋。

企劃專案核心欄位：

1. 專案屬性 (project_attributes)：
   - industry: 客戶所屬產業
   - campaign: 行銷活動主題
   - is_urgent: 是否為急案 (true/false/null)

2. 時間與預算 (time_budget)：
   - planning_due_date: 提案交付日期
   - campaign_start_date: 活動開始日期
   - campaign_end_date: 活動結束日期
   - budget: 專案總預算

3. 內容與策略 (content_strategy)：
   - planning_types: 企劃類型陣列 (可選：前端洞察分析、策略提案、產品包裝、市場趨勢分析、創意版位製作、文案撰寫)
   - media_formats: 投放形式
   - audience_lock: 受眾鎖定
   - audience_behavior: 受眾行為與分析
   - client_materials: 客戶素材
   - client_requests: 客戶要求

4. 技術需求 (technical_needs)：
   - technical_needs: 技術需求描述

你必須嚴格按照以下 JSON 格式返回，不要添加任何其他內容：

{
  "project_attributes": {
    "industry": "提取的產業或待確認",
    "campaign": "提取的活動名稱或待確認",
    "is_urgent": null
  },
  "time_budget": {
    "planning_due_date": "提取的日期或待確認",
    "campaign_start_date": "提取的日期或待確認",
    "campaign_end_date": "待確認",
    "budget": "提取的預算或待確認"
  },
  "content_strategy": {
    "planning_types": ["提取的類型1", "提取的類型2"],
    "media_formats": "提取的投放形式或待確認",
    "audience_lock": "提取的受眾鎖定或待確認",
    "audience_behavior": "提取的受眾行為或待確認",
    "client_materials": "待確認",
    "client_requests": "待確認"
  },
  "technical_needs": {
    "technical_needs": "待確認"
  }
}

記住：只返回 JSON，不要其他內容！"""

    @staticmethod
    def get_project_clarification_prompt() -> str:
        """獲取企劃專案澄清問題提示詞"""
        return """你是一個專業的企劃專案分析助手。基於已提取的企劃專案資料和原始需求，生成澄清問題。

請分析以下企劃專案相關方面並生成問題：
1. 標記為"待確認"的企劃專案欄位（優先處理）
2. 缺失的企劃專案核心欄位
3. 模糊或不完整的企劃資訊
4. 需要進一步確認的企劃細節
5. 可能影響企劃專案執行的關鍵資訊

特別注意：
- 如果發現"待確認"項目，請針對這些項目生成具體的澄清問題
- 問題應該具體明確，容易回答
- 每個問題應該針對一個特定的企劃專案欄位
- 問題數量控制在3-5個，避免過多問題
- 重要：不要在問題中列出選項（如A、B、C或選項列表），選項會由前端動態顯示
- 問題應該專注於收集資訊，而不是提供選擇題

返回格式：
[
  "問題1",
  "問題2",
  "問題3"
]

記住：只返回 JSON 陣列，不要其他內容！"""

    @staticmethod
    def get_planning_proposal_generation_prompt() -> str:
        """獲取企劃專案提案生成提示詞"""
        return """你是一個專業的企劃專案提案生成助手。基於完整的企劃專案資料，生成格式化的企劃提案文本。

請根據提供的企劃專案資料，生成包含以下內容的提案：
1. 專案概覽（活動名稱、產業、緊急程度）
2. 時程與預算規劃
3. 內容與策略說明
4. 技術需求描述
5. 提案內容（市場分析、競品分析、策略提案等）
6. 後續步驟

重要：你必須生成完整的 Markdown 格式提案文本，包含所有必要的企劃專案內容。

記住：只返回格式化的提案文本，不要其他內容！"""


# 工具執行器
class PlanningAgent:
    """
    管理企劃專案業務流程，負責調用 ToolExecutor、LLMClient、SystemPrompts，並處理流程控制。
    """

    def __init__(self):
        self.llm_client = LLMClient()
        self.tool_executor = ToolExecutor()

    def analyze_requirement(self, requirement: str) -> Dict[str, Any]:
        """分析企劃專案需求完整性"""
        system_prompt = SystemPrompts.get_planning_requirement_analysis_prompt()
        prompt = f"{system_prompt}\n\n企劃需求描述：{requirement}"

        try:
            response = self.llm_client.generate_response(prompt)
            logger.info(f"LLM 原始回應: {response}")

            # 嘗試解析 JSON
            try:
                result = json.loads(response)
                logger.info(
                    f"直接解析成功: {json.dumps(result, ensure_ascii=False, indent=2)}"
                )
            except json.JSONDecodeError as e:
                logger.warning(f"直接解析失敗，嘗試清理回應: {e}")
                # 如果直接解析失敗，嘗試清理回應
                cleaned_response = clean_json_response(response)
                logger.info(f"清理後回應: {cleaned_response}")

                try:
                    result = json.loads(cleaned_response)
                    logger.info(
                        f"清理後解析成功: {json.dumps(result, ensure_ascii=False, indent=2)}"
                    )
                except json.JSONDecodeError as e2:
                    logger.error(f"清理後仍然解析失敗: {e2}")
                    logger.error(f"原始回應: {response}")
                    logger.error(f"清理後回應: {cleaned_response}")
                    raise HTTPException(
                        status_code=500, detail=f"解析 LLM 回應失敗: {str(e2)}"
                    )

            return result
        except HTTPException:
            # 重新拋出 HTTPException
            raise
        except Exception as e:
            logger.error(f"企劃專案需求分析失敗: {e}")
            raise HTTPException(
                status_code=500, detail=f"企劃專案需求分析失敗: {str(e)}"
            )

    def extract_project_data(self, requirement: str) -> Dict[str, Any]:
        """提取企劃專案結構化資料"""
        system_prompt = SystemPrompts.get_project_extraction_prompt()
        prompt = f"{system_prompt}\n\n用戶需求：{requirement}"

        try:
            response = self.llm_client.generate_response(prompt)
            logger.info(f"LLM 原始回應: {response}")

            # 解析回應
            try:
                # 嘗試直接解析
                project_data = json.loads(response)
                logger.info(
                    f"解析的企劃專案資料: {json.dumps(project_data, ensure_ascii=False, indent=2)}"
                )
            except json.JSONDecodeError as e:
                logger.warning(f"直接解析失敗，嘗試清理回應: {e}")

                # 嘗試清理回應（移除 markdown 標記等）
                cleaned_response = clean_json_response(response)

                try:
                    project_data = json.loads(cleaned_response)
                    logger.info(
                        f"清理後解析成功: {json.dumps(project_data, ensure_ascii=False, indent=2)}"
                    )
                except json.JSONDecodeError as e2:
                    logger.error(f"清理後仍然解析失敗: {e2}")
                    logger.error(f"原始回應: {response}")
                    logger.error(f"清理後回應: {cleaned_response}")
                    raise HTTPException(status_code=500, detail="解析 LLM 回應失敗")

            return project_data
        except Exception as e:
            logger.error(f"提取企劃專案資料失敗: {e}")
            raise HTTPException(
                status_code=500, detail=f"提取企劃專案資料失敗: {str(e)}"
            )

    def generate_clarification_questions(
        self, requirement: str, missing_elements: List[str]
    ) -> List[str]:
        """生成企劃專案澄清問題"""
        system_prompt = SystemPrompts.get_planning_clarification_questions_prompt()
        prompt = f"{system_prompt}\n\n企劃需求描述：{requirement}\n缺失元素：{', '.join(missing_elements)}"

        try:
            response = self.llm_client.generate_response(prompt)

            # 嘗試解析 JSON
            try:
                questions = json.loads(response)
            except json.JSONDecodeError:
                # 如果直接解析失敗，嘗試清理回應
                cleaned_response = clean_json_response(response)
                questions = json.loads(cleaned_response)

            return questions if isinstance(questions, list) else []
        except Exception as e:
            logger.error(f"生成企劃專案澄清問題失敗: {e}")
            return ["請提供更多關於企劃專案的詳細資訊"]

    def generate_project_clarification_questions(
        self,
        requirement: str,
        project_data: Dict[str, Any],
        completeness_result: Dict[str, Any] = None,
    ) -> List[str]:
        """生成企劃專案澄清問題"""
        system_prompt = SystemPrompts.get_project_clarification_prompt()

        # 如果有完整性結果，特別針對"待確認"項目生成問題
        if completeness_result and completeness_result.get(
            "has_pending_confirmation", False
        ):
            pending_fields = completeness_result.get("pending_confirmation_fields", [])
            prompt = f"{system_prompt}\n\n原始需求：{requirement}\n已提取資料：{json.dumps(project_data, ensure_ascii=False, indent=2)}\n\n特別注意：以下欄位標記為'待確認'，請針對這些欄位生成具體的澄清問題：{', '.join(pending_fields)}"
        else:
            prompt = f"{system_prompt}\n\n原始需求：{requirement}\n已提取資料：{json.dumps(project_data, ensure_ascii=False, indent=2)}"

        try:
            response = self.llm_client.generate_response(prompt)

            # 嘗試解析 JSON
            try:
                questions = json.loads(response)
            except json.JSONDecodeError:
                # 如果直接解析失敗，嘗試清理回應
                cleaned_response = clean_json_response(response)
                questions = json.loads(cleaned_response)

            return questions if isinstance(questions, list) else []
        except Exception as e:
            logger.error(f"生成企劃專案澄清問題失敗: {e}")
            # 如果有待確認項目，生成針對性的問題
            if completeness_result and completeness_result.get(
                "has_pending_confirmation", False
            ):
                pending_fields = completeness_result.get(
                    "pending_confirmation_fields", []
                )
                questions = []
                for field in pending_fields[:5]:  # 最多5個問題
                    category, field_name = field.split(".", 1)
                    questions.append(f"請提供{category}中的{field_name}的具體資訊")
                return questions
            return ["請提供更多關於企劃專案的詳細資訊"]

    def compute_completeness(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """計算企劃專案資料完整性"""
        logger.info(f"執行 compute_completeness")

        total_fields = 0
        filled_fields = 0
        missing_fields = []
        pending_confirmation_fields = []

        # 檢查所有核心欄位
        for category, fields in PROJECT_CORE_FIELDS.items():
            if category in project_data:
                for field in fields:
                    total_fields += 1
                    field_value = project_data[category].get(field)
                    if field_value and field_value != "待確認" and field_value != "":
                        filled_fields += 1
                    elif field_value == "待確認":
                        pending_confirmation_fields.append(f"{category}.{field}")
                        missing_fields.append(f"{category}.{field}")
                    else:
                        missing_fields.append(f"{category}.{field}")
            else:
                total_fields += len(fields)
                missing_fields.extend([f"{category}.{field}" for field in fields])

        completeness_score = filled_fields / total_fields if total_fields > 0 else 0

        result = {
            "completeness_score": completeness_score,
            "filled_fields": filled_fields,
            "total_fields": total_fields,
            "missing_fields": missing_fields,
            "pending_confirmation_fields": pending_confirmation_fields,
            "completeness_percentage": f"{completeness_score * 100:.1f}%",
            "has_pending_confirmation": len(pending_confirmation_fields) > 0,
        }

        logger.info(f"完整性計算結果: {result}")
        return result

    def decide_tool_action(
        self, requirement: str, completeness_result: Dict[str, Any]
    ) -> str:
        """決定應該執行哪個工具 - 專注於企劃專案"""
        logger.info(f"執行 decide_tool_action")

        # 檢查是否為企劃專案需求
        planning_keywords = [
            "企劃",
            "行銷",
            "廣告",
            "活動",
            "宣傳",
            "推廣",
            "品牌",
            "產品上市",
            "campaign",
            "marketing",
            "advertising",
            "promotion",
            "branding",
            "媒體",
            "投放",
            "受眾",
            "策略",
            "創意",
            "文案",
            "洞察",
            "分析",
            "提案",
        ]

        # 檢查是否包含企劃相關關鍵字
        is_planning_project = False
        for keyword in planning_keywords:
            if keyword in requirement:
                is_planning_project = True
                break

        logger.info(f"企劃需求: {requirement}")
        logger.info(f"是否為企劃專案: {is_planning_project}")
        logger.info(f"完整性評分: {completeness_result.get('completeness_score', 0)}")
        logger.info(
            f"有待確認項目: {completeness_result.get('has_pending_confirmation', False)}"
        )

        # 檢查是否有"待確認"項目
        if completeness_result.get("has_pending_confirmation", False):
            logger.info("發現待確認項目，決定執行 ask_clarification")
            return "ask_clarification"

        # 所有需求都視為企劃專案需求，因為系統已專注於企劃
        if completeness_result["completeness_score"] >= COMPLETENESS_THRESHOLD:
            logger.info("決定執行 create_planning_project")
            return "create_planning_project"
        else:
            logger.info("決定執行 ask_clarification")
            return "ask_clarification"

    def render_proposal_text(self, planning_project: PlanningProject) -> str:
        """根據完整的企劃專案物件生成格式化的提案文本"""
        return self.tool_executor.render_proposal_text(planning_project)

    def create_planning_project(
        self, project_data: Dict[str, Any], user_id: str, original_requirement: str
    ) -> PlanningProject:
        """創建完整的企劃專案物件"""
        return self.tool_executor.create_planning_project(
            project_data, user_id, original_requirement
        )

    def save_to_chroma(self, planning_project: PlanningProject) -> ChromaSaveResult:
        """儲存企劃專案到 Chroma 向量資料庫"""
        return self.tool_executor.save_to_chroma(planning_project)


class ToolExecutor:
    """
    工具執行器 - 只負責單一工具的執行，不負責流程控制
    """

    def __init__(self):
        self.llm_client = LLMClient()

    @monitor_performance
    def create_planning_project(
        self, project_data: Dict[str, Any], user_id: str, original_requirement: str
    ) -> PlanningProject:
        """創建完整的企劃專案物件"""
        logger.info(f"執行 create_planning_project")

        # 確保所有必要的資料都有預設值
        project_attrs = project_data.get("project_attributes", {})
        time_budget = project_data.get("time_budget", {})
        content_strategy = project_data.get("content_strategy", {})
        technical_needs = project_data.get("technical_needs", {})

        # 創建 PlanningProject 物件
        planning_project = PlanningProject(
            project_attributes=ProjectAttributes(**project_attrs),
            time_budget=TimeBudget(**time_budget),
            content_strategy=ContentStrategy(**content_strategy),
            technical_needs=TechnicalNeeds(**technical_needs),
            user_id=user_id,
            original_requirement=original_requirement,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        logger.info(f"創建企劃專案物件: {planning_project.dict()}")
        return planning_project

    @monitor_performance
    def save_to_chroma(self, planning_project: PlanningProject) -> ChromaSaveResult:
        """儲存企劃專案到 Chroma 向量資料庫"""
        logger.info(f"執行 save_to_chroma")

        try:
            # 這裡應該實作實際的 Chroma 儲存邏輯
            # 目前先模擬儲存成功
            document_id = f"project_{planning_project.user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 準備儲存的資料
            document_data = {
                "id": document_id,
                "user_id": planning_project.user_id,
                "project_data": planning_project.dict(),
                "metadata": {
                    "created_at": planning_project.created_at,
                    "updated_at": planning_project.updated_at,
                    "project_type": "planning_project",
                },
            }

            # TODO: 實作實際的 Chroma 儲存
            # chroma_client.add_documents([document_data])

            result = ChromaSaveResult(
                success=True,
                document_id=document_id,
                saved_at=datetime.now().isoformat(),
            )

            logger.info(f"Chroma 儲存成功: {result.dict()}")
            return result

        except Exception as e:
            logger.error(f"Chroma 儲存失敗: {e}")
            return ChromaSaveResult(
                success=False, error_message=str(e), saved_at=datetime.now().isoformat()
            )

    @monitor_performance
    def render_proposal_text(self, planning_project: PlanningProject) -> str:
        """根據完整的企劃專案物件生成格式化的提案文本"""
        logger.info(f"執行 render_proposal_text")

        # 使用 LLM 生成提案文本
        system_prompt = SystemPrompts.get_planning_proposal_generation_prompt()

        # 準備企劃專案資料
        project_data = {
            "project_attributes": planning_project.project_attributes.dict(),
            "time_budget": planning_project.time_budget.dict(),
            "content_strategy": planning_project.content_strategy.dict(),
            "technical_needs": planning_project.technical_needs.dict(),
        }

        prompt = f"{system_prompt}\n\n企劃專案資料：{json.dumps(project_data, ensure_ascii=False, indent=2)}"

        try:
            response = self.llm_client.generate_response(prompt)
            logger.info(f"生成提案文本，長度: {len(response)} 字符")
            return response
        except Exception as e:
            logger.error(f"生成提案文本失敗: {e}")
            # 如果 LLM 生成失敗，使用備用的模板生成
            return self._generate_fallback_proposal_text(planning_project)

    def _generate_fallback_proposal_text(
        self, planning_project: PlanningProject
    ) -> str:
        """備用的提案文本生成方法"""
        # 提取專案資料
        project_attrs = planning_project.project_attributes
        time_budget = planning_project.time_budget
        content_strategy = planning_project.content_strategy
        technical_needs = planning_project.technical_needs

        # 處理企劃類型
        planning_types = content_strategy.planning_types
        planning_types_str = ", ".join(planning_types) if planning_types else "待確認"

        # 生成格式化的提案文本
        proposal_text = f"""# 企劃專案提案

## 📋 專案概覽
**活動名稱**: {project_attrs.campaign}
**產業類別**: {project_attrs.industry}
**緊急程度**: {'急案' if project_attrs.is_urgent else '一般案件'}

## ⏰ 時程與預算
**提案交付日期**: {time_budget.planning_due_date}
**活動開始日期**: {time_budget.campaign_start_date}
**活動結束日期**: {time_budget.campaign_end_date}
**專案總預算**: {time_budget.budget}

## 🎯 內容與策略
**企劃類型**: {planning_types_str}
**投放形式**: {content_strategy.media_formats}
**目標受眾**: {content_strategy.audience_lock}
**受眾行為分析**: {content_strategy.audience_behavior}

## 📦 客戶資源
**客戶素材**: {content_strategy.client_materials}
**客戶要求**: {content_strategy.client_requests}

## 🔧 技術需求
{technical_needs.technical_needs}

## 📊 提案內容

### 市場分析
需進一步了解目標市場現況、競爭態勢及機會點。

### 競品分析
需進一步了解主要競爭對手分析及差異化策略。

### 策略提案
基於 {planning_types_str} 的整合行銷策略規劃。

### 媒體規劃
{content_strategy.media_formats} 投放策略及媒體組合。

### 預算及預估成效
預算 {time_budget.budget}，預估成效需進一步評估。

### 時程規劃
{time_budget.planning_due_date} 至 {time_budget.campaign_end_date} 的執行時程。

### 技術需求
{technical_needs.technical_needs}

### 風險評估
需進一步了解專案執行風險及應對策略。

### 後續步驟
1. 需求確認與簽署
2. 詳細企劃書製作
3. 創意發想與製作
4. 媒體投放執行
5. 成效監測與優化

---
*提案生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*專案編號: {planning_project.user_id}_{datetime.now().strftime('%Y%m%d')}*
"""

        logger.info(f"使用備用方法生成提案文本，長度: {len(proposal_text)} 字符")
        return proposal_text


# 全域工具執行器
tool_executor = ToolExecutor()


# API 端點
@app.get("/health")
async def health_check():
    """健康檢查"""
    try:
        # 檢查 Ollama 服務
        llm_client = LLMClient()
        models = llm_client.list_models()
        return {
            "status": "healthy",
            "ollama_available": True,
            "available_models": len(models),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "ollama_available": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@app.get("/models")
async def list_models():
    """獲取可用模型列表"""
    try:
        llm_client = LLMClient()
        models = llm_client.list_models()
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取模型列表失敗: {str(e)}")


@app.post("/intake", response_model=AgentOutput)
async def intake_requirement(request: IntakeRequest):
    """企劃專案需求攝入分析"""
    try:
        # 使用 PlanningAgent 處理業務流程
        planning_agent = PlanningAgent()

        # 1. 提取企劃專案結構化資料
        project_data = planning_agent.extract_project_data(request.requirement)

        # 2. 計算完整性（包含"待確認"項目檢查）
        completeness_result = planning_agent.compute_completeness(project_data)

        # 3. 決定工具動作
        tool_action = planning_agent.decide_tool_action(
            request.requirement, completeness_result
        )

        logger.info(f"決定的工具動作: {tool_action}")

        # 4. 根據工具動作執行相應的處理
        if tool_action == "ask_clarification":
            # 需要澄清問題
            clarification_questions = (
                planning_agent.generate_project_clarification_questions(
                    request.requirement, project_data, completeness_result
                )
            )

            # 創建臨時的企劃專案用於顯示
            temp_planning_project = planning_agent.create_planning_project(
                project_data, request.user_id, request.requirement
            )

            # 生成臨時的提案文本
            temp_proposal_text = planning_agent.render_proposal_text(
                temp_planning_project
            )

            return AgentOutput(
                completeness_report=completeness_result,
                clarification_questions=clarification_questions,
                proposal_text=temp_proposal_text,
                status="需要澄清",
                tool_action="詢問澄清",
                planning_project=temp_planning_project.dict(),
            )

        else:
            # 資料完整，創建完整的企劃專案
            planning_project = planning_agent.create_planning_project(
                project_data, request.user_id, request.requirement
            )

            # 儲存到 Chroma
            chroma_result = planning_agent.save_to_chroma(planning_project)

            # 生成格式化的提案文本
            proposal_text = planning_agent.render_proposal_text(planning_project)

            return AgentOutput(
                completeness_report=completeness_result,
                proposal_text=proposal_text,
                saved_to_chroma=chroma_result.dict(),
                status="完成",
                tool_action="創建企劃專案",
                planning_project=planning_project.dict(),
            )

    except HTTPException:
        # 重新拋出 HTTPException
        raise
    except Exception as e:
        logger.error(f"企劃專案需求攝入失敗: {e}")
        import traceback

        logger.error(f"詳細錯誤: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"企劃專案需求攝入失敗: {str(e)}")


@app.post("/clarify", response_model=AgentOutput)
async def clarify_requirement(request: ClarifyRequest):
    """企劃專案澄清"""
    try:
        # 使用 PlanningAgent 處理業務流程
        planning_agent = PlanningAgent()

        # 重新分析企劃專案需求（包含澄清答案）
        enhanced_requirement = (
            f"{request.original_requirement}\n\n澄清答案：\n"
            + "\n".join([f"- {answer}" for answer in request.clarification_answers])
        )

        # 1. 提取企劃專案結構化資料
        project_data = planning_agent.extract_project_data(enhanced_requirement)

        # 2. 計算完整性（包含"待確認"項目檢查）
        completeness_result = planning_agent.compute_completeness(project_data)

        # 3. 決定工具動作
        tool_action = planning_agent.decide_tool_action(
            enhanced_requirement, completeness_result
        )

        # 4. 根據工具動作執行相應的處理
        if tool_action == "ask_clarification":
            # 仍然需要澄清問題
            clarification_questions = (
                planning_agent.generate_project_clarification_questions(
                    enhanced_requirement, project_data, completeness_result
                )
            )

            # 創建臨時的企劃專案用於顯示
            temp_planning_project = planning_agent.create_planning_project(
                project_data, request.user_id, request.original_requirement
            )

            # 生成臨時的提案文本
            temp_proposal_text = planning_agent.render_proposal_text(
                temp_planning_project
            )

            return AgentOutput(
                completeness_report=completeness_result,
                clarification_questions=clarification_questions,
                proposal_text=temp_proposal_text,
                status="need_clarification",
                tool_action="ask_clarification",
                planning_project=temp_planning_project.dict(),
            )

        else:
            # 資料完整，創建完整的企劃專案
            planning_project = planning_agent.create_planning_project(
                project_data, request.user_id, request.original_requirement
            )

            # 儲存到 Chroma
            chroma_result = planning_agent.save_to_chroma(planning_project)

            # 生成格式化的提案文本
            proposal_text = planning_agent.render_proposal_text(planning_project)

            return AgentOutput(
                completeness_report=completeness_result,
                proposal_text=proposal_text,
                saved_to_chroma=chroma_result.dict(),
                status="完成",
                tool_action="創建企劃專案",
                planning_project=planning_project.dict(),
            )

    except Exception as e:
        logger.error(f"企劃專案澄清失敗: {e}")
        raise HTTPException(status_code=500, detail=f"企劃專案澄清失敗: {str(e)}")


@app.post("/project-intake", response_model=AgentOutput)
async def project_intake_requirement(request: ProjectIntakeRequest):
    """企劃專案需求攝入"""
    try:
        # 使用 PlanningAgent 處理業務流程
        planning_agent = PlanningAgent()

        # 1. 提取企劃專案結構化資料
        project_data = planning_agent.extract_project_data(request.requirement)

        # 2. 計算資料完整性
        completeness_result = planning_agent.compute_completeness(project_data)

        # 3. 決定工具動作
        tool_action = planning_agent.decide_tool_action(
            request.requirement, completeness_result
        )

        # 4. 根據工具動作執行相應的處理
        if tool_action == "ask_clarification":
            # 需要澄清問題
            clarification_questions = (
                planning_agent.generate_project_clarification_questions(
                    request.requirement, project_data, completeness_result
                )
            )

            # 生成臨時提案模板（顯示已提取的資料）
            temp_planning_project = planning_agent.create_planning_project(
                project_data, request.user_id, request.requirement
            )
            temp_proposal_text = planning_agent.render_proposal_text(
                temp_planning_project
            )

            return AgentOutput(
                completeness_report=completeness_result,
                proposal_text=temp_proposal_text,
                clarification_questions=clarification_questions,
                status="需要澄清",
                tool_action="詢問澄清",
                planning_project=temp_planning_project.dict(),
            )
        else:
            # 資料完整，創建完整的企劃專案
            planning_project = planning_agent.create_planning_project(
                project_data, request.user_id, request.requirement
            )

            # 儲存到 Chroma
            chroma_result = planning_agent.save_to_chroma(planning_project)

            # 生成格式化的提案文本
            proposal_text = planning_agent.render_proposal_text(planning_project)

            return AgentOutput(
                completeness_report=completeness_result,
                proposal_text=proposal_text,
                saved_to_chroma=chroma_result.dict(),
                status="完成",
                tool_action="創建企劃專案",
                planning_project=planning_project.dict(),
            )

    except Exception as e:
        logger.error(f"企劃專案需求攝入失敗: {e}")
        raise HTTPException(status_code=500, detail=f"企劃專案需求攝入失敗: {str(e)}")


@app.post("/project-clarify", response_model=AgentOutput)
async def project_clarify_requirement(request: ProjectClarifyRequest):
    """企劃專案澄清"""
    try:
        # 使用 PlanningAgent 處理業務流程
        planning_agent = PlanningAgent()

        # 1. 重新提取企劃專案資料（包含澄清答案）
        enhanced_requirement = (
            f"{request.original_requirement}\n\n澄清答案：\n"
            + "\n".join([f"- {answer}" for answer in request.clarification_answers])
        )

        project_data = planning_agent.extract_project_data(enhanced_requirement)

        # 2. 計算更新後的完整性
        completeness_result = planning_agent.compute_completeness(project_data)

        # 3. 創建完整的企劃專案
        planning_project = planning_agent.create_planning_project(
            project_data, request.user_id, request.original_requirement
        )

        # 4. 儲存到 Chroma
        chroma_result = planning_agent.save_to_chroma(planning_project)

        # 5. 生成最終格式化的提案文本
        proposal_text = planning_agent.render_proposal_text(planning_project)

        return AgentOutput(
            completeness_report=completeness_result,
            proposal_text=proposal_text,
            saved_to_chroma=chroma_result.dict(),
            status="完成",
        )

    except Exception as e:
        logger.error(f"企劃專案澄清失敗: {e}")
        raise HTTPException(status_code=500, detail=f"企劃專案澄清失敗: {str(e)}")


@app.post("/ask-clarification")
async def ask_clarification_endpoint(request: ClarificationRequest):
    """專門處理澄清問題的端點"""
    try:
        # 使用 PlanningAgent 處理業務流程
        planning_agent = PlanningAgent()

        # 簡化處理：直接返回問題列表
        return {
            "success": True,
            "questions": request.questions,
            "user_id": request.user_id,
            "context": request.context,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"處理澄清問題失敗: {e}")
        raise HTTPException(status_code=500, detail=f"處理澄清問題失敗: {str(e)}")


# ---------- 對話式功能輔助函數 ----------
def group_questions_from_pending(pending: List[str]) -> List[str]:
    """將相關的欄位分組，生成更智能的問題"""
    s = set(pending or [])
    qs: List[str] = []

    # 活動期間
    if "time_budget.campaign_start_date" in s and "time_budget.campaign_end_date" in s:
        qs.append(
            "請一次提供【活動期間】的開始與結束日期，"
            "格式如 2025/01/01 至 2025/03/31。"
        )
        s.discard("time_budget.campaign_start_date")
        s.discard("time_budget.campaign_end_date")

    # 交付與預算
    if "time_budget.planning_due_date" in s and "time_budget.budget" in s:
        qs.append("請提供【提案交付日期】與【預算金額】（如 200 萬）。")
        s.discard("time_budget.planning_due_date")
        s.discard("time_budget.budget")

    # 產業＋主題
    if "project_attributes.industry" in s and "project_attributes.campaign" in s:
        qs.append("請說明【產業類別】與本次【活動主題/Campaign】。")
        s.discard("project_attributes.industry")
        s.discard("project_attributes.campaign")

    # 媒體與企劃類型
    if "content_strategy.media_formats" in s and "content_strategy.planning_types" in s:
        qs.append(
            "預計採用的【媒體形式】與【企劃類型】為何？" "可多選，直接以逗號分隔。"
        )
        s.discard("content_strategy.media_formats")
        s.discard("content_strategy.planning_types")

    # 其餘逐一詢問
    for key in list(s):
        label = FRIENDLY_FIELD_NAMES.get(key, key.split(".")[-1])
        if key.endswith("is_urgent"):
            qs.append("此案是否為急案？（是/否）")
        elif key.endswith("campaign_start_date"):
            qs.append("請提供【活動開始日期】（YYYY/MM/DD）。")
        elif key.endswith("campaign_end_date"):
            qs.append("請提供【活動結束日期】（YYYY/MM/DD）。")
        elif key.endswith("planning_due_date"):
            qs.append("請提供【提案交付日期】（YYYY/MM/DD）。")
        elif key.endswith("budget"):
            qs.append("此案【預算金額】為多少？可填整數（如 200 萬）。")
        else:
            qs.append(f"請補充「{label}」的具體內容。")
    return qs


def _compose_enhanced_requirement(original: str, answers: List[str]) -> str:
    """組合原始需求和澄清答案"""
    if not answers:
        return original
    joined = "\n".join(f"- {a}" for a in answers)
    return f"""{original}

澄清答案：
{joined}"""


def _update_project_data_from_answers(
    project_data: Dict[str, Any], answers: List[str]
) -> Dict[str, Any]:
    """根據用戶回答智能更新專案資料"""
    if not answers:
        return project_data

    updated_data = project_data.copy()

    for answer in answers:
        answer_lower = answer.lower().strip()

        # 處理產業相關回答
        if any(keyword in answer_lower for keyword in ["動物園", "zoo", "動物"]):
            if "project_attributes" not in updated_data:
                updated_data["project_attributes"] = {}
            updated_data["project_attributes"]["industry"] = "旅遊觀光"
            updated_data["project_attributes"]["campaign"] = answer.strip()
        elif any(
            keyword in answer_lower for keyword in ["食品", "飲料", "食物", "餐飲"]
        ):
            if "project_attributes" not in updated_data:
                updated_data["project_attributes"] = {}
            updated_data["project_attributes"]["industry"] = "食品飲料"
            updated_data["project_attributes"]["campaign"] = answer.strip()
        elif any(keyword in answer_lower for keyword in ["科技", "3c", "數位", "軟體"]):
            if "project_attributes" not in updated_data:
                updated_data["project_attributes"] = {}
            updated_data["project_attributes"]["industry"] = "科技產業"
            updated_data["project_attributes"]["campaign"] = answer.strip()
        elif any(
            keyword in answer_lower for keyword in ["金融", "保險", "銀行", "投資"]
        ):
            if "project_attributes" not in updated_data:
                updated_data["project_attributes"] = {}
            updated_data["project_attributes"]["industry"] = "金融保險"
            updated_data["project_attributes"]["campaign"] = answer.strip()

        # 處理「是否急案」的回答
        if "不是急案" in answer or "不急" in answer or "一般" in answer:
            if "project_attributes" not in updated_data:
                updated_data["project_attributes"] = {}
            updated_data["project_attributes"]["is_urgent"] = False
        elif "是急案" in answer or "急" in answer or "緊急" in answer:
            if "project_attributes" not in updated_data:
                updated_data["project_attributes"] = {}
            updated_data["project_attributes"]["is_urgent"] = True

        # 處理預算相關回答
        if "萬" in answer and any(char.isdigit() for char in answer):
            digits = "".join(char for char in answer if char.isdigit())
            if digits:
                if "time_budget" not in updated_data:
                    updated_data["time_budget"] = {}
                updated_data["time_budget"]["budget"] = int(digits)

        # 處理日期相關回答
        if "年" in answer and "月" in answer and "日" in answer:
            # 簡單的日期提取邏輯
            if "time_budget" not in updated_data:
                updated_data["time_budget"] = {}
            # 這裡可以添加更複雜的日期解析邏輯

    return updated_data


def generate_quick_replies(
    completeness_score: float,
    missing_keys: List[str],
    project_data: Dict[str, Any] = None,
) -> List[str]:
    """根據當前狀態生成智能快速回覆選項"""
    option_manager = SmartOptionManager()
    return option_manager.get_smart_quick_replies(
        completeness_score, missing_keys, project_data
    )


# ---------- 智能選項管理端點 ----------
@app.get("/options/{field_key}")
def get_field_options(field_key: str, max_count: int = Query(5, ge=1, le=10)):
    """獲取特定欄位的預定義選項"""
    try:
        option_manager = SmartOptionManager()
        options = option_manager.get_field_specific_options(field_key, max_count)

        if not options:
            raise HTTPException(
                status_code=404, detail=f"找不到欄位 {field_key} 的預定義選項"
            )

        return {
            "field_key": field_key,
            "options": options,
            "count": len(options),
            "description": option_manager.option_rules.get(field_key, {}).get(
                "description", ""
            ),
        }
    except Exception as e:
        logger.error(f"獲取欄位選項失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取欄位選項失敗: {str(e)}")


@app.get("/options/contextual")
def get_contextual_options(
    missing_keys: List[str] = Query([]),
    completeness_score: float = Query(0.0, ge=0.0, le=1.0),
):
    """獲取上下文相關的選項"""
    try:
        option_manager = SmartOptionManager()
        options = option_manager.get_contextual_options(missing_keys)

        return {
            "missing_keys": missing_keys,
            "completeness_score": completeness_score,
            "contextual_options": options,
            "count": len(options),
        }
    except Exception as e:
        logger.error(f"獲取上下文選項失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取上下文選項失敗: {str(e)}")


# ---------- 對話式功能端點 ----------
@app.post("/chat/message", response_model=ChatTurnResponse)
def chat_message(payload: ChatMessage):
    """主要的對話端點，處理用戶訊息並返回回應"""
    try:
        planning_agent = PlanningAgent()

        # Create or fetch session
        if payload.session_id and payload.session_id in SESSIONS:
            sess = SESSIONS[payload.session_id]
            is_new = False
        else:
            sess = ChatSession(
                session_id=str(uuid.uuid4())[:8],
                user_id=payload.user_id,
                original_requirement=(payload.message or "").strip(),
            )
            SESSIONS[sess.session_id] = sess
            is_new = True

        # Prepare text and update answers
        if not is_new and payload.message.strip():
            sess.answers.append(payload.message.strip())

        enhanced = (
            sess.original_requirement
            if is_new
            else _compose_enhanced_requirement(sess.original_requirement, sess.answers)
        )

        # Always recalculate completeness after any changes
        project_data = planning_agent.extract_project_data(enhanced)

        # 智能更新專案資料（基於用戶回答）
        if not is_new and sess.answers:
            project_data = _update_project_data_from_answers(project_data, sess.answers)

        comp = planning_agent.compute_completeness(project_data)
        pending = (
            comp.get("pending_confirmation_fields")
            or comp.get("missing_required_keys")
            or comp.get("missing_fields")
            or comp.get("missing_elements")
            or []
        )

        sess.missing_keys = pending
        sess.completeness_score = float(comp.get("completeness_score", 0.0))
        sess.has_pending_confirmation = bool(comp.get("has_pending_confirmation"))
        sess.updated_at = datetime.now().isoformat()

        # Always produce a draft
        planning_project = planning_agent.create_planning_project(
            project_data, sess.user_id, enhanced
        )
        proposal_text = planning_agent.render_proposal_text(planning_project)
        sess.planning_project = planning_project.dict()
        sess.proposal_text = proposal_text

        # 確保專案資料被正確更新到session中
        sess.project_data = project_data

        need_more = (
            (comp.get("tool_action") == "ask_clarification")
            or sess.has_pending_confirmation
            or sess.completeness_score < THRESHOLD
        )

        if need_more:
            gqs = group_questions_from_pending(pending)
            raw_qs = (
                planning_agent.generate_project_clarification_questions(
                    enhanced, project_data, comp
                )
                or []
            )
            qs = gqs or raw_qs or ["請描述此專案的產業類別與主要目標受眾"]
            next_q = next((q for q in qs if q not in sess.asked_questions), qs[0])
            sess.last_question = next_q
            sess.asked_questions.append(next_q)

            quick_replies = generate_quick_replies(
                sess.completeness_score, sess.missing_keys, sess.planning_project
            )

            return ChatTurnResponse(
                session_id=sess.session_id,
                role="assistant",
                message=next_q,
                status="需要澄清",
                completeness_score=sess.completeness_score,
                missing_keys=sess.missing_keys,
                asked_questions=sess.asked_questions,
                next_question=sess.last_question,
                planning_project=sess.planning_project,
                proposal_text=sess.proposal_text,
                quick_replies=quick_replies,
            )

        # 如果專案資料足夠完整，給出完整的企劃建議
        if sess.completeness_score >= 0.7:  # 70%以上完整度
            industry = sess.planning_project.get("project_attributes", {}).get(
                "industry", ""
            )
            campaign = sess.planning_project.get("project_attributes", {}).get(
                "campaign", ""
            )

            if industry and campaign:
                # 根據產業和活動生成完整的企劃建議
                if "旅遊觀光" in industry or "動物園" in campaign.lower():
                    complete_message = f"""好的，身為{industry}產業的一員，要推廣{campaign}這個明星項目，我們可以運用一套有系統、具創意且可執行的策略。

首先，我們需要一個強而有力的核心概念，讓所有行銷活動都圍繞著它。

主題：「溫柔的巨獸，比你想像的更靠近」(Gentle Giants, Closer Than You Think)

這個主題有雙重含義：
• 物理上的靠近：在動物園，你可以親眼見到牠們，感受牠們的巨大與優雅。
• 情感與知識上的靠近：透過我們的推廣，你將會了解牠們不為人知的一面，從心靈上更親近牠們。

接下來，我們需要確定：
1. 目標受眾是誰？（親子家庭、學生團體、情侶約會等）
2. 主要推廣管道？（社群媒體、戶外廣告、KOL合作等）
3. 預算範圍？（建議10-50萬起）
4. 活動時程？（建議3-6個月）

請告訴我這些細節，我就能為您制定完整的行銷企劃！"""
                else:
                    complete_message = f"""很好！基於您提供的{industry}產業資訊和{campaign}活動，我已經有了初步的企劃方向。

現在讓我們完善以下關鍵要素：
1. 目標受眾定位
2. 主要推廣管道
3. 預算範圍
4. 活動時程

請提供這些資訊，我將為您制定完整的行銷策略！"""

                quick_replies = generate_quick_replies(
                    sess.completeness_score, sess.missing_keys, sess.planning_project
                )

                return ChatTurnResponse(
                    session_id=sess.session_id,
                    role="assistant",
                    message=complete_message,
                    status="企劃建議",
                    completeness_score=sess.completeness_score,
                    missing_keys=sess.missing_keys,
                    asked_questions=sess.asked_questions,
                    next_question=None,
                    planning_project=sess.planning_project,
                    proposal_text=sess.proposal_text,
                    quick_replies=quick_replies,
                )

        return ChatTurnResponse(
            session_id=sess.session_id,
            role="assistant",
            message="完成需求彙整，已產出提案",
            status="完成",
            completeness_score=sess.completeness_score,
            missing_keys=sess.missing_keys,
            asked_questions=sess.asked_questions,
            planning_project=sess.planning_project,
            proposal_text=sess.proposal_text,
        )

    except Exception as e:
        logger.error(f"chat_message error: {e}")
        raise HTTPException(status_code=500, detail=f"處理對話失敗: {str(e)}")


@app.post("/chat/autofill", response_model=ChatTurnResponse)
def chat_autofill(payload: ChatMessage):
    """Fill missing required fields with AI assumptions, then produce a concrete proposal."""
    try:
        planning_agent = PlanningAgent()
        if payload.session_id and payload.session_id in SESSIONS:
            sess = SESSIONS[payload.session_id]
        else:
            sess = ChatSession(
                session_id=str(uuid.uuid4())[:8],
                user_id=payload.user_id,
                original_requirement=(payload.message or "").strip() or "（未提供）",
            )
            SESSIONS[sess.session_id] = sess

        enhanced = _compose_enhanced_requirement(
            sess.original_requirement, sess.answers
        )

        project_data = planning_agent.extract_project_data(enhanced)
        comp = planning_agent.compute_completeness(project_data)
        pending = (
            comp.get("pending_confirmation_fields")
            or comp.get("missing_required_keys")
            or comp.get("missing_fields")
            or comp.get("missing_elements")
            or []
        )

        if not pending:
            planning_project = planning_agent.create_planning_project(
                project_data, sess.user_id, enhanced
            )
            proposal_text = planning_agent.render_proposal_text(planning_project)
            sess.planning_project = planning_project.dict()
            sess.proposal_text = proposal_text
            return ChatTurnResponse(
                session_id=sess.session_id,
                role="assistant",
                message="欄位已完整，直接產出提案。",
                status="完成",
                completeness_score=1.0,
                missing_keys=[],
                asked_questions=sess.asked_questions,
                planning_project=sess.planning_project,
                proposal_text=sess.proposal_text,
            )

        # 使用 PlanningAgent 的 LLM 來補全
        llm = planning_agent.llm_client
        prompt = (
            "你是資深行銷企劃。根據資料，請只補齊缺漏欄位，並提供 Assumptions。"
            "輸出**純 JSON**。\n\n"
            f"=== 原始需求 ===\n{sess.original_requirement}\n\n"
            f"=== 澄清答案 ===\n{chr(10).join(sess.answers) if sess.answers else '（無）'}\n\n"
            f"=== 當前資料 ===\n{json.dumps(project_data, ensure_ascii=False, indent=2)}\n\n"
            f"=== 需補欄位 ===\n{json.dumps(pending, ensure_ascii=False)}\n\n"
            '{"filled": { 僅包含缺漏欄位的巢狀鍵值 }, "assumptions": ["..."] }'
        )

        raw = llm.generate_response(prompt)
        try:
            data = json.loads(raw)
        except Exception:
            raw = llm.generate_response(prompt + "\n\n只允許回傳 JSON，不要任何說明。")
            data = json.loads(raw)

        filled = data.get("filled", {}) or {}

        # 合併資料
        merged = {
            "project_attributes": project_data.get("project_attributes", {}) or {},
            "time_budget": project_data.get("time_budget", {}) or {},
            "content_strategy": project_data.get("content_strategy", {}) or {},
            "technical_needs": project_data.get("technical_needs", {}) or {},
            "original_requirement": sess.original_requirement,
        }

        # 深度合併
        for k, v in filled.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k].update(v)
            else:
                merged[k] = v

        comp2 = planning_agent.compute_completeness(merged)
        pending2 = comp2.get("pending_confirmation_fields") or []
        planning_project = planning_agent.create_planning_project(
            merged, sess.user_id, enhanced
        )
        proposal_text = planning_agent.render_proposal_text(planning_project)

        sess.planning_project = planning_project.dict()
        sess.proposal_text = proposal_text
        sess.completeness_score = float(comp2.get("completeness_score", 0.99))
        sess.missing_keys = pending2
        sess.has_pending_confirmation = False

        msg = "已用合理假設補齊缺漏欄位並完成提案。"
        if data.get("assumptions"):
            msg += " 主要假設：" + "；".join(data["assumptions"][:5])

        return ChatTurnResponse(
            session_id=sess.session_id,
            role="assistant",
            message=msg,
            status="完成",
            completeness_score=sess.completeness_score,
            missing_keys=sess.missing_keys,
            asked_questions=sess.asked_questions,
            planning_project=sess.planning_project,
            proposal_text=sess.proposal_text,
        )

    except Exception as e:
        logger.error(f"chat_autofill error: {e}")
        raise HTTPException(status_code=500, detail=f"假設補全失敗: {str(e)}")


@app.post("/chat/open-extract", response_model=ChatTurnResponse)
def chat_open_extract(payload: ChatMessage):
    """使用開放域抽取器的對話端點"""
    try:
        # 獲取或創建會話
        if payload.session_id and payload.session_id in SESSIONS:
            sess = SESSIONS[payload.session_id]
        else:
            sess = ChatSession(
                session_id=str(uuid.uuid4())[:8],
                user_id=payload.user_id or "anonymous",
                original_requirement=(payload.message or "").strip(),
            )
            SESSIONS[sess.session_id] = sess

        # 獲取已知資料
        known = sess.planning_project or {}

        # 使用開放域抽取器
        ext = llm_open_extract(payload.message, known)

        # 寫入 non-high-level 的 known_delta
        for k, v in (ext.get("known_delta") or {}).items():
            if k not in ["project.industry", "project.theme", "geo", "brand"] and v:
                _set_nested(known, k, v)

        # 產生自然句與動態按鈕
        coach_text, actions = open_build_actions(ext, known)

        # 更新完整度（使用現有邏輯）
        # 這裡需要實現 compute_completeness 函數或使用現有的
        comp_score = 0.5  # 暫時使用固定值，實際應該計算
        missing_fields = []  # 暫時使用空列表，實際應該計算

        # 更新會話資料
        sess.planning_project = known
        sess.completeness_score = comp_score
        sess.missing_keys = missing_fields
        sess.updated_at = datetime.now().isoformat()

        return ChatTurnResponse(
            session_id=sess.session_id,
            role="assistant",
            message=coach_text,
            status="OK",
            completeness_score=sess.completeness_score,
            missing_keys=sess.missing_keys,
            asked_questions=sess.asked_questions or [],
            planning_project=known,
            quick_actions=actions,
        )

    except Exception as e:
        logger.error(f"chat_open_extract error: {e}")
        raise HTTPException(status_code=500, detail=f"開放域抽取處理失敗: {str(e)}")


@app.get("/chat/sessions/{session_id}")
def get_session(session_id: str):
    """獲取特定會話的詳細資訊"""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="會話不存在")
    return SESSIONS[session_id]


@app.get("/chat/sessions")
def list_sessions():
    """列出所有會話（用於管理）"""
    return {
        "total_sessions": len(SESSIONS),
        "sessions": [
            {
                "session_id": sess.session_id,
                "user_id": sess.session_id,
                "original_requirement": (
                    sess.original_requirement[:100] + "..."
                    if len(sess.original_requirement) > 100
                    else sess.original_requirement
                ),
                "completeness_score": sess.completeness_score,
                "created_at": sess.created_at,
                "updated_at": sess.updated_at,
            }
            for sess in SESSIONS.values()
        ],
    }


@app.delete("/chat/sessions/{session_id}")
def delete_session(session_id: str):
    """刪除特定會話"""
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="會話不存在")
    del SESSIONS[session_id]
    return {"message": "會話已刪除"}


# =============================
# Audience Coach Constants & Helpers (from app_coach.py)
# =============================

# Audience Coach specific constants
AUDIENCE_QR = [
    "再行銷 7天",
    "再行銷 30天",
    "類似受眾 1%",
    "類似受眾 3%",
    "興趣 美妝",
    "興趣 3C",
    "情境 加到購物車未結帳",
    "情境 觀看產品頁超過30秒",
    "排除 既有客戶",
    "關鍵字 建議範例",
    "我不知道 給我範例",
]


def audience_coach_message() -> str:
    """受眾教練引導訊息"""
    return (
        "先把受眾講人話，回答三件事。\n"
        "一，情境，例如 加到購物車未結帳 或 觀看產品頁超過30秒。\n"
        "二，人群，例如 女25到34，上班族，重視保養。\n"
        "三，鎖定方式，例如 再行銷7天，加上 類似受眾1%。\n"
        "可以照這個格式回，或直接點下面的選項。\n"
        "範例：情境 觀看產品頁超過30秒，人群 女25到34 上班族，鎖定 再行銷7天 類似受眾1%，排除 既有客戶。"
    )


def _append_unique(lst: List[str], items: List[str]):
    """添加唯一項目到列表"""
    for it in items:
        it = str(it).strip()
        if it and it not in lst:
            lst.append(it)


def _parse_date_zh(text: str) -> Optional[str]:
    """解析中文日期格式"""
    import re

    # accept YYYY/MM/DD or YYYY-MM-DD
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        dt = datetime(y, mo, d)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _after(text: str, keys: List[str]) -> Optional[str]:
    """提取關鍵字後的內容"""
    import re

    for k in keys:
        idx = text.find(k)
        if idx >= 0:
            s = text[idx + len(k) :]
            # 去除前導符號
            s = re.sub(r"^[：:\s，,]+", "", s)
            # 擷取到句號或換行
            s = re.split(r"[。;\n]", s)[0]
            return s.strip()
    return None


def _split_list(s: str) -> List[str]:
    """分割列表字符串"""
    import re

    parts = re.split(r"[、,，/｜\| ]+", s.strip())
    parts = [p for p in parts if p]
    return parts


def _get_nested(d: Dict[str, Any], path: str) -> Any:
    """獲取嵌套字典的值"""
    cur = d
    parts = path.split(".")
    for p in parts:
        if isinstance(cur, list):
            return None
        if p not in cur:
            return None
        cur = cur[p]
    return cur


def _set_nested(d: Dict[str, Any], path: str, value: Any) -> None:
    """設置嵌套字典的值"""
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], (dict, list)):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _ensure_cs(
    pd: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """確保內容策略結構存在"""
    if "content_strategy" not in pd:
        pd["content_strategy"] = {}
    cs = pd["content_strategy"]
    if "audience_behavior" not in cs:
        cs["audience_behavior"] = {}
    ab = cs["audience_behavior"]
    ab.setdefault("scenarios", [])
    ab.setdefault("interests", [])
    ab.setdefault("keywords", [])
    ab.setdefault("demographic", {})
    ab.setdefault("exclusions", [])
    return pd, cs, ab


def parse_and_update_from_answer(pd: Dict[str, Any], answer: str) -> Dict[str, Any]:
    """解析用戶回答並更新專案資料 (受眾教練版本)"""
    import re

    pd, cs, ab = _ensure_cs(pd)

    # 預算
    m = re.search(
        r"(?:(?:總)?預算|budget)[：:\s]*([0-9][0-9,\.]*)(?:\s*萬)?",
        answer,
        flags=re.IGNORECASE,
    )
    if m and not cs.get("budget"):
        val = m.group(1).replace(",", "")
        try:
            num = float(val)
            # 支援「200萬」類型，若後綴出現"萬"則乘以 10000
            if "萬" in answer[m.start() : m.end()]:
                num = int(num * 10000)
            _set_nested(pd, "time_budget.budget", int(num))
        except Exception:
            pass

    # 起訖日期
    m2 = re.search(
        r"(\d{4}[/-]\d{1,2}[/-]\d{1,2})\s*(?:至|~|-|—)\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
        answer,
    )
    if m2:
        s = _parse_date_zh(m2.group(1))
        e = _parse_date_zh(m2.group(2))
        if s:
            _set_nested(pd, "time_budget.campaign_start_date", s)
        if e:
            _set_nested(pd, "time_budget.campaign_end_date", e)
    else:
        # 單獨提供
        s = _parse_date_zh(answer)
        if s and not _get_nested(pd, "time_budget.campaign_start_date"):
            _set_nested(pd, "time_budget.campaign_start_date", s)

    # 交付日期
    m3 = re.search(
        r"(?:交付|截稿|due)[：:\s]*([0-9]{4}[/-]\d{1,2}[/-]\d{1,2})",
        answer,
        flags=re.IGNORECASE,
    )
    if m3:
        d = _parse_date_zh(m3.group(1))
        if d:
            _set_nested(pd, "time_budget.planning_due_date", d)

    # 產業 / 主題
    if any(k in answer for k in ["產業", "industry"]):
        seg = _after(answer, ["產業", "industry"])
        if seg:
            _set_nested(pd, "project_attributes.industry", seg)
    if any(k in answer for k in ["主題", "campaign"]):
        seg = _after(answer, ["主題", "campaign"])
        if seg:
            _set_nested(pd, "project_attributes.campaign", seg)

    # 直接產業識別：如果用戶直接說出產業名稱
    if not pd.get("project_attributes", {}).get("industry"):
        if any(
            k in answer
            for k in [
                "動物園",
                "zoo",
                "動物",
                "觀光",
                "旅遊",
                "餐飲",
                "電商",
                "科技",
                "金融",
                "教育",
                "醫療",
                "房地產",
                "汽車",
                "服飾",
                "美妝",
            ]
        ):
            # 直接設定產業
            if "動物園" in answer or "zoo" in answer.lower() or "動物" in answer:
                _set_nested(pd, "project_attributes.industry", "旅遊觀光")
                _set_nested(pd, "project_attributes.campaign", answer.strip())
            elif "觀光" in answer or "旅遊" in answer:
                _set_nested(pd, "project_attributes.industry", "觀光旅遊")
            elif "餐飲" in answer:
                _set_nested(pd, "project_attributes.industry", "餐飲")
            elif "電商" in answer:
                _set_nested(pd, "project_attributes.industry", "電商")
            elif "科技" in answer:
                _set_nested(pd, "project_attributes.industry", "科技")
            elif "金融" in answer:
                _set_nested(pd, "project_attributes.industry", "金融")
            elif "教育" in answer:
                _set_nested(pd, "project_attributes.industry", "教育")
            elif "醫療" in answer:
                _set_nested(pd, "project_attributes.industry", "醫療")
            elif "房地產" in answer:
                _set_nested(pd, "project_attributes.industry", "房地產")
            elif "汽車" in answer:
                _set_nested(pd, "project_attributes.industry", "汽車")
            elif "服飾" in answer:
                _set_nested(pd, "project_attributes.industry", "服飾")
            elif "美妝" in answer:
                _set_nested(pd, "project_attributes.industry", "美妝")

    # 智能識別：如果用戶回答包含受眾相關詞彙，可能是回答受眾問題
    if any(
        k in answer
        for k in [
            "遊客",
            "客戶",
            "受眾",
            "族群",
            "人群",
            "家庭",
            "親子",
            "上班族",
            "學生",
        ]
    ):
        # 檢查是否在回答受眾相關問題
        if not pd.get("project_attributes", {}).get("industry"):
            # 如果產業還沒設定，嘗試從上下文推斷
            if any(k in answer for k in ["國內", "外國", "觀光", "旅遊"]):
                _set_nested(pd, "project_attributes.industry", "觀光旅遊")
            elif any(k in answer for k in ["親子", "家庭", "兒童"]):
                _set_nested(pd, "project_attributes.industry", "親子娛樂")
            elif any(k in answer for k in ["上班族", "企業", "商務"]):
                _set_nested(pd, "project_attributes.industry", "企業服務")

        # 設定受眾族群
        if "國內" in answer and "外國" in answer:
            _append_unique(ab["demographics"], ["國內遊客", "外國遊客"])
        elif "國內" in answer:
            _append_unique(ab["demographics"], ["國內遊客"])
        elif "外國" in answer:
            _append_unique(ab["demographics"], ["外國遊客"])
        elif "親子" in answer or "家庭" in answer:
            _append_unique(ab["demographics"], ["家庭親子"])
        elif "高端" in answer:
            _append_unique(ab["demographics"], ["高端客戶"])

    # 媒體 / 企劃
    if "媒體" in answer or "media" in answer.lower():
        seg = _after(answer, ["媒體", "media"])
        if seg:
            items = _split_list(seg)
            if items:
                _set_nested(pd, "content_strategy.media_formats", items)
    if "企劃" in answer or "planning" in answer.lower():
        seg = _after(answer, ["企劃", "planning"])
        if seg:
            items = _split_list(seg)
            if items:
                _set_nested(pd, "content_strategy.planning_types", items)

    # 受眾：鎖定與行為
    # 再行銷天數
    m = re.search(r"(再行銷|retarget|重定向)\s*(\d+)\s*天", answer, re.IGNORECASE)
    if m:
        cur = cs.get("audience_lock") or ""
        addon = f"再行銷 {m.group(2)}天"
        if addon not in cur:
            cs["audience_lock"] = (cur + " " + addon).strip()

    # 類似受眾百分比
    m = re.search(r"(類似受眾|lookalike)\s*(\d+)\s*%", answer, re.IGNORECASE)
    if m:
        cur = cs.get("audience_lock") or ""
        addon = f"類似受眾 {m.group(2)}%"
        if addon not in cur:
            cs["audience_lock"] = (cur + " " + addon).strip()

    # 情境
    for seg in re.findall(r"(?:情境|事件)[：:\s]+([^,，。]+)", answer):
        _append_unique(ab["scenarios"], [seg])

    # 興趣
    for seg in re.findall(r"(?:興趣)[：:\s]+([^,，。]+)", answer):
        parts = _split_list(seg)
        _append_unique(ab["interests"], parts)

    # 關鍵字
    for seg in re.findall(r"(?:關鍵字)[：:\s]+([^。]+)", answer):
        tokens = re.findall(r"[\"\"\"]?([\w\u4e00-\u9fa5\+\- ]+)[\"\"\"]?", seg)
        _append_unique(ab["keywords"], [t for t in tokens if t.strip()])

    # 排除
    for seg in re.findall(r"(?:排除)[：:\s]+([^,，。]+)", answer):
        _append_unique(ab["exclusions"], [seg])

    # 性別
    if any(k in answer for k in ["男", "男性"]):
        ab["demographic"]["gender"] = "male"
    if any(k in answer for k in ["女", "女性"]):
        ab["demographic"]["gender"] = "female"
    # 年齡
    m = re.search(r"(\d{2})\s*[到~\-–至]\s*(\d{2})\s*歲", answer)
    if m:
        ab["demographic"]["age_min"] = int(m.group(1))
        ab["demographic"]["age_max"] = int(m.group(2))

    return pd


def generate_audience_quick_replies(
    completeness_score: float, missing_keys: List[str]
) -> List[str]:
    """生成受眾教練快速回覆選項"""
    missing = set(missing_keys or [])
    needs_audience = any(
        k in missing
        for k in [
            "content_strategy.audience_lock",
            "content_strategy.audience_behavior.scenarios",
            "content_strategy.audience_behavior.interests",
            "content_strategy.audience_behavior.demographic",
        ]
    )
    if needs_audience:
        return AUDIENCE_QR[:]

    qr = []
    if completeness_score < 0.5:
        qr.extend(["我想先了解基本資訊", "請幫我分析需求完整性", "我需要範例參考"])
    elif completeness_score < 0.8:
        qr.extend(["繼續補充細節", "我想看看目前的提案", "幫我檢查還缺什麼"])
    else:
        qr.extend(["完成需求彙整", "產出最終提案", "儲存到專案池"])
    return qr


def group_audience_questions_from_pending(pending: List[str]) -> List[str]:
    """將相關的受眾欄位分組，生成更智能的問題"""
    s = set(pending or [])
    qs: List[str] = []

    # 受眾教練優先 - 但不要總是返回相同的訊息
    need_audience = any(
        k in s
        for k in [
            "content_strategy.audience_lock",
            "content_strategy.audience_behavior.scenarios",
            "content_strategy.audience_behavior.interests",
            "content_strategy.audience_behavior.demographic",
        ]
    )
    if need_audience:
        # 根據缺失的欄位生成更具體的問題
        if "content_strategy.audience_behavior.scenarios" in s:
            qs.append(
                "請描述目標受眾的典型使用情境，例如：加到購物車未結帳、觀看產品頁超過30秒"
            )
        if "content_strategy.audience_behavior.demographic" in s:
            qs.append("請描述目標受眾的基本特徵，例如：女25至34歲、上班族、重視品質")
        if "content_strategy.audience_behavior.interests" in s:
            qs.append("請描述目標受眾的興趣愛好，例如：3C產品、美妝保養、運動健身")
        if "content_strategy.audience_lock" in s:
            qs.append("請描述受眾鎖定策略，例如：再行銷7天、類似受眾1%、排除既有客戶")

        # 移除已處理的欄位
        s.discard("content_strategy.audience_lock")
        s.discard("content_strategy.audience_behavior.scenarios")
        s.discard("content_strategy.audience_behavior.interests")
        s.discard("content_strategy.audience_behavior.demographic")

    # 活動期間
    if "time_budget.campaign_start_date" in s and "time_budget.campaign_end_date" in s:
        qs.append("請一次提供活動期間，格式 2025/01/01 至 2025/03/31。")
        s.discard("time_budget.campaign_start_date")
        s.discard("time_budget.campaign_end_date")

    # 交付與預算
    if "time_budget.planning_due_date" in s and "time_budget.budget" in s:
        qs.append("請提供提案交付日期與總預算，例如 2025/01/15，200萬。")
        s.discard("time_budget.planning_due_date")
        s.discard("time_budget.budget")

    # 產業與主題
    if "project_attributes.industry" in s and "project_attributes.campaign" in s:
        qs.append("請說明產業類別與本次活動主題。")
        s.discard("project_attributes.industry")
        s.discard("project_attributes.campaign")

    # 媒體與企劃類型
    if "content_strategy.media_formats" in s and "content_strategy.planning_types" in s:
        qs.append("預計採用的媒體形式與企劃類型，可多選，用逗號分隔。")
        s.discard("content_strategy.media_formats")
        s.discard("content_strategy.planning_types")

    # 其餘逐一
    for key in list(s):
        if key.endswith("is_urgent"):
            qs.append("此案是否為急案，是或否。")
        elif key.endswith("campaign_start_date"):
            qs.append("請提供活動開始日期，YYYY/MM/DD。")
        elif key.endswith("campaign_end_date"):
            qs.append("請提供活動結束日期，YYYY/MM/DD。")
        elif key.endswith("planning_due_date"):
            qs.append("請提供提案交付日期，YYYY/MM/DD。")
        elif key.endswith("budget"):
            qs.append("總預算多少，可填整數，例如 200萬。")
        else:
            label = FRIENDLY_FIELD_NAMES.get(key, key.split(".")[-1])
            qs.append(f"請補充「{label}」的具體內容。")
    return qs


# =============================
# Audience Coach Models
# =============================


class AudienceCoachState(BaseModel):
    """受眾教練會話狀態"""

    project_data: Dict[str, Any] = Field(default_factory=dict)
    messages: List[Dict[str, str]] = Field(default_factory=list)
    last_question: Optional[str] = None


class AudienceCoachChatIn(BaseModel):
    """受眾教練聊天輸入"""

    session_id: str = Field(default="default")
    user_message: str


class AudienceCoachChatOut(BaseModel):
    """受眾教練聊天輸出"""

    message: str
    next_question: Optional[str] = None
    quick_replies: List[str] = []
    project_data: Dict[str, Any] = {}
    completeness_score: float = 0.0
    missing_keys: List[str] = []


# =============================
# Audience Coach Session Storage
# =============================

# 受眾教練會話存儲
AUDIENCE_COACH_SESSIONS: Dict[str, AudienceCoachState] = {}


def get_audience_coach_state(session_id: str) -> AudienceCoachState:
    """獲取受眾教練會話狀態"""
    if session_id not in AUDIENCE_COACH_SESSIONS:
        AUDIENCE_COACH_SESSIONS[session_id] = AudienceCoachState(
            project_data=_new_audience_coach_project_data(),
            messages=[],
            last_question=None,
        )
    return AUDIENCE_COACH_SESSIONS[session_id]


def _new_audience_coach_project_data() -> Dict[str, Any]:
    """創建新的受眾教練專案資料結構"""
    return {
        "project_attributes": {"industry": None, "campaign": None},
        "time_budget": {
            "campaign_start_date": None,
            "campaign_end_date": None,
            "planning_due_date": None,
            "budget": None,
        },
        "content_strategy": {
            "media_formats": [],  # e.g., ["短影音","部落客合作"]
            "planning_types": [],  # e.g., ["策略提案","創意版位製作"]
            "audience_lock": None,  # e.g., "再行銷 7天 類似受眾 1%"
            "audience_behavior": {
                "scenarios": [],  # e.g., ["觀看產品頁超過30秒"]
                "interests": [],  # e.g., ["美妝","3C"]
                "keywords": [],  # optional
                "demographic": {},  # { gender: "female", age_min: 25, age_max: 34 }
                "exclusions": [],  # e.g., ["既有客戶"]
            },
        },
    }


def _calc_audience_coach_completeness(pd: Dict[str, Any]) -> Tuple[float, List[str]]:
    """計算受眾教練專案資料完整性"""
    # 使用 app_coach.py 的 REQUIRED_KEYS
    REQUIRED_KEYS = [
        "project_attributes.industry",
        "project_attributes.campaign",
        "time_budget.campaign_start_date",
        "time_budget.campaign_end_date",
        "time_budget.planning_due_date",
        "time_budget.budget",
        "content_strategy.media_formats",
        "content_strategy.planning_types",
        "content_strategy.audience_lock",
        "content_strategy.audience_behavior.scenarios",
        "content_strategy.audience_behavior.interests",
        "content_strategy.audience_behavior.demographic",
    ]

    missing = []
    filled = 0
    for k in REQUIRED_KEYS:
        val = _get_nested(pd, k)
        ok = False
        if isinstance(val, str):
            ok = bool(val.strip())
        elif isinstance(val, (int, float)):
            ok = True
        elif isinstance(val, list):
            ok = len(val) > 0
        elif isinstance(val, dict):
            ok = len(val.keys()) > 0
        else:
            ok = val is not None
        if ok:
            filled += 1
        else:
            missing.append(k)
    score = round(filled / len(REQUIRED_KEYS), 3)
    return score, missing


# =============================
# Audience Coach API Endpoints
# =============================


@app.get("/audience-coach/state")
def get_audience_coach_current_state(session_id: str = Query("default")):
    """獲取受眾教練當前狀態"""
    st = get_audience_coach_state(session_id)
    score, missing = _calc_audience_coach_completeness(st.project_data)
    return {
        "project_data": st.project_data,
        "messages": st.messages[-50:],
        "completeness_score": score,
        "missing_keys": missing,
        "next_question": st.last_question,
    }


@app.post("/audience-coach/reset")
def reset_audience_coach(session_id: str = Body("default")):
    """重置受眾教練會話"""
    AUDIENCE_COACH_SESSIONS[session_id] = AudienceCoachState(
        project_data=_new_audience_coach_project_data(), messages=[], last_question=None
    )
    return {"ok": True}


# 移除重複的端點定義，保留增強版
# @app.post("/audience-coach/chat", response_model=AudienceCoachChatOut)
# def audience_coach_chat(inp: AudienceCoachChatIn):
#     """受眾教練聊天端點 - 已移除，使用增強版"""
#     pass


# =============================
# Enhanced Audience Coach with Ollama Integration
# =============================


class EnhancedAudienceCoach:
    """增強版受眾教練，整合 Ollama 智能生成功能"""

    def __init__(self):
        self.llm_client = LLMClient()

    def generate_audience_insights(
        self, project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用 Ollama 生成受眾洞察分析"""
        system_prompt = """你是一個專業的受眾分析專家。基於提供的專案資料，生成深入的受眾洞察分析。

請分析以下方面：
1. 受眾行為模式分析
2. 興趣偏好深度挖掘
3. 消費習慣分析
4. 媒體使用偏好
5. 競品受眾分析
6. 受眾觸達策略建議

返回格式：
{
  "audience_insights": {
    "behavior_patterns": ["洞察1", "洞察2"],
    "interest_analysis": "深度興趣分析",
    "consumption_habits": "消費習慣描述",
    "media_preferences": ["媒體偏好1", "媒體偏好2"],
    "competitor_audience": "競品受眾分析",
    "reach_strategy": "觸達策略建議"
  },
  "recommendations": ["建議1", "建議2", "建議3"]
}

記住：只返回 JSON，不要其他內容！"""

        prompt = f"{system_prompt}\n\n專案資料：{json.dumps(project_data, ensure_ascii=False, indent=2)}"

        try:
            response = self.llm_client.generate_response(prompt)
            return json.loads(response)
        except Exception as e:
            logger.error(f"生成受眾洞察失敗: {e}")
            return self._generate_fallback_insights(project_data)

    def generate_audience_questions(
        self, project_data: Dict[str, Any], missing_keys: List[str]
    ) -> List[str]:
        """使用 Ollama 生成智能受眾問題"""
        system_prompt = """你是一個專業的受眾分析專家。基於專案資料和缺失的受眾資訊，生成智能的澄清問題。

請生成 3-5 個針對受眾分析的具體問題，問題應該：
1. 針對缺失的受眾資訊
2. 基於產業特性和活動目標
3. 有助於深入了解目標受眾
4. 具體明確且容易回答
5. 符合行銷企劃的專業需求

返回格式：
[
  "問題1",
  "問題2", 
  "問題3"
]

記住：只返回 JSON 陣列，不要其他內容！"""

        prompt = f"{system_prompt}\n\n專案資料：{json.dumps(project_data, ensure_ascii=False, indent=2)}\n\n缺失的受眾資訊：{', '.join(missing_keys)}"

        try:
            response = self.llm_client.generate_response(prompt)
            questions = json.loads(response)
            return questions if isinstance(questions, list) else []
        except Exception as e:
            logger.error(f"生成受眾問題失敗: {e}")
            return self._generate_fallback_questions(missing_keys)

    def generate_audience_strategy(
        self, project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用 Ollama 生成受眾策略建議"""
        system_prompt = """你是一個專業的行銷策略專家。基於專案資料和受眾分析，生成完整的受眾策略建議。

請提供以下策略建議：
1. 受眾定位策略
2. 觸達渠道組合
3. 內容策略建議
4. 投放時機建議
5. 預算分配建議
6. 成效評估指標

返回格式：
{
  "audience_strategy": {
    "targeting_strategy": "受眾定位策略描述",
    "channel_mix": ["渠道1", "渠道2", "渠道3"],
    "content_strategy": "內容策略建議",
    "timing_recommendations": "投放時機建議",
    "budget_allocation": "預算分配建議",
    "kpi_metrics": ["指標1", "指標2", "指標3"]
  },
  "implementation_steps": ["步驟1", "步驟2", "步驟3"]
}

記住：只返回 JSON，不要其他內容！"""

        prompt = f"{system_prompt}\n\n專案資料：{json.dumps(project_data, ensure_ascii=False, indent=2)}"

        try:
            response = self.llm_client.generate_response(prompt)
            return json.loads(response)
        except Exception as e:
            logger.error(f"生成受眾策略失敗: {e}")
            return self._generate_fallback_strategy(project_data)

    def _generate_fallback_insights(
        self, project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """備用的受眾洞察生成"""
        return {
            "audience_insights": {
                "behavior_patterns": ["基於產業特性的基礎洞察"],
                "interest_analysis": "需要進一步分析",
                "consumption_habits": "待深入了解",
                "media_preferences": ["數位媒體", "社交平台"],
                "competitor_audience": "建議進行競品分析",
                "reach_strategy": "多渠道觸達策略",
            },
            "recommendations": [
                "建議進行深度受眾訪談",
                "建議分析競品受眾",
                "建議進行A/B測試",
            ],
        }

    def _generate_fallback_questions(self, missing_keys: List[str]) -> List[str]:
        """備用的問題生成"""
        questions = []
        for key in missing_keys[:5]:
            if "audience" in key:
                questions.append(f"請詳細描述目標受眾的{key.split('.')[-1]}")
            elif "scenarios" in key:
                questions.append("請描述目標受眾的典型使用情境")
            elif "interests" in key:
                questions.append("請描述目標受眾的主要興趣愛好")
            else:
                questions.append(f"請補充{key}的相關資訊")
        return questions

    def _generate_fallback_strategy(
        self, project_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """備用的策略生成"""
        return {
            "audience_strategy": {
                "targeting_strategy": "基於產業特性的基礎定位策略",
                "channel_mix": ["數位廣告", "社交媒體", "內容行銷"],
                "content_strategy": "建議進行內容測試和優化",
                "timing_recommendations": "建議根據受眾活躍時間投放",
                "budget_allocation": "建議預算分配給效果最好的渠道",
                "kpi_metrics": ["觸達率", "互動率", "轉換率"],
            },
            "implementation_steps": [
                "制定詳細執行計劃",
                "設置監控指標",
                "進行效果測試",
            ],
        }


# 創建增強版受眾教練實例
enhanced_audience_coach = EnhancedAudienceCoach()


# 升級受眾教練快速回覆生成
def generate_enhanced_audience_quick_replies(
    completeness_score: float, missing_keys: List[str], project_data: Dict[str, Any]
) -> List[str]:
    m = set(missing_keys or [])
    qr: List[str] = []

    # 受眾三件事：情境、人群、鎖定方式
    if {
        "content_strategy.audience_behavior.scenarios",
        "content_strategy.audience_behavior.interests",
        "content_strategy.audience_behavior.demographic",
        "content_strategy.audience_lock",
    } & m:
        # 情境
        if "content_strategy.audience_behavior.scenarios" in m:
            qr += [
                "情境 加到購物車未結帳",
                "情境 觀看產品頁超過30秒",
                "情境 搜尋品牌關鍵字",
            ]
        # 人群（依已有資料補全）
        if "content_strategy.audience_behavior.demographic" in m:
            qr += [
                "人群 女25至34 上班族",
                "人群 男25至44 科技從業",
                "人群 家庭主婦 育兒關注",
            ]
        # 興趣
        if "content_strategy.audience_behavior.interests" in m:
            qr += ["興趣 3C", "興趣 美妝保養", "興趣 運動健身"]
        # 鎖定
        if "content_strategy.audience_lock" in m:
            qr += ["鎖定 再行銷7天", "鎖定 再行銷30天", "鎖定 類似受眾1%"]

    # 檔期與預算
    if {"time_budget.campaign_start_date", "time_budget.campaign_end_date"} & m:
        qr += ["活動期間 2025/09/16 至 2025/10/31", "活動期間 2025/11/01 至 2025/12/31"]
    if "time_budget.budget" in m:
        qr += ["總預算 200 萬", "總預算 80 萬"]

    # 媒體型式
    if "content_strategy.media_formats" in m:
        qr += ["投放 影音短片 社群貼文 聯播網橫幅", "投放 KOL合作 部落客評測"]

    # 兜底：門檻分段
    if not qr:
        if completeness_score < 0.5:
            qr += ["我想先了解基本資訊", "請幫我分析需求完整性", "我需要範例參考"]
        elif completeness_score < 0.8:
            qr += ["繼續補充細節", "我想看看目前的提案", "幫我檢查還缺什麼"]
        else:
            qr += ["完成需求彙整", "產出最終提案", "儲存到專案池"]

    # 去重，保留順序
    seen = set()
    dedup = []
    for s in qr:
        if s not in seen:
            seen.add(s)
            dedup.append(s)
    return dedup[:12]  # 避免一次太多


# 升級受眾教練問題生成
def generate_enhanced_audience_questions(
    project_data: Dict[str, Any], missing_keys: List[str]
) -> List[str]:
    """生成增強版受眾教練問題"""
    # 優先使用穩定的本地邏輯，避免 Ollama 不穩定
    local_questions = group_audience_questions_from_pending(missing_keys)

    # 如果本地邏輯沒有問題，直接返回
    if local_questions:
        return local_questions

    # 只有在本地邏輯無法處理時，才嘗試使用 Ollama
    try:
        questions = enhanced_audience_coach.generate_audience_questions(
            project_data, missing_keys
        )
        if questions and isinstance(questions, list) and len(questions) > 0:
            return questions
    except Exception as e:
        logger.error(f"生成智能問題失敗: {e}")

    # 最終回退：生成基本的受眾問題
    return ["請描述目標受眾的基本特徵", "請說明受眾的使用情境", "請描述受眾的興趣偏好"]


# 升級受眾教練聊天端點
@app.post("/audience-coach/chat", response_model=AudienceCoachChatOut)
def enhanced_audience_coach_chat(inp: AudienceCoachChatIn):
    """增強版受眾教練聊天端點"""
    st = get_audience_coach_state(inp.session_id)
    user_text = inp.user_message.strip()

    if not user_text:
        return AudienceCoachChatOut(
            message="請輸入內容。",
            next_question=st.last_question,
            quick_replies=[],
            project_data=st.project_data,
            completeness_score=_calc_audience_coach_completeness(st.project_data)[0],
            missing_keys=_calc_audience_coach_completeness(st.project_data)[1],
        )

    # 記錄使用者訊息
    st.messages.append({"role": "user", "content": user_text})

    # 嘗試解析並更新資料
    st.project_data = parse_and_update_from_answer(st.project_data, user_text)

    # 計算缺口與建議問題
    score, missing = _calc_audience_coach_completeness(st.project_data)

    # 使用增強版問題生成
    questions = generate_enhanced_audience_questions(st.project_data, missing)

    # AI 回覆邏輯 - 優先使用 Ollama 生成動態回應
    ai_msg = None
    try:
        # 嘗試使用 Ollama 生成智能回應
        if missing and len(missing) > 0:
            # 構建智能提示 - 使用精簡微回合廣告企劃教練 prompt
            smart_prompt = f"""你是廣告企劃教練，採「微回合」：每回合只推進一小步。
禁止寒暄、禁止長前言、不要條列一大坨。

【輸出格式，嚴格遵守】
可見區只寫兩行，依序：
提示：<≤30字，先一句白話解釋為何這題重要>
問題：<只問一件事，專注於收集資訊，不要列出選項>

注意：不要輸出選項列表，選項會由前端動態顯示

最後輸出 <STATE>…</STATE>，內容是 JSON：
{{
  "known_delta": {{ 本回合新確定欄位 }},
  "missing_top": [ 3-5 個待補欄位鍵 ],
  "next_intent": "ask|draft",
  "completeness": 0.0~1.0
}}

【欄位集合】
project.industry, project.theme, objective, kpi,
audience.scenario, audience.demographic, audience.lock, audience.interest,
media.formats, media.platforms, time.start, time.end, budget.total, geo, offer

規則：一次只問一件事，先解釋再提問；日期 YYYY/MM/DD，金額整數元；
高層欄位（project.industry, project.theme）先視為候選，除非使用者明確確認才列入 known_delta。

【已知（精簡）】
{json.dumps({k: v for k, v in st.project_data.items() if v}, ensure_ascii=False)}

【缺口Top】
{json.dumps(missing[:5], ensure_ascii=False)}

【使用者剛說】
{user_text}

請嚴格依格式輸出。"""

            # 調用 Ollama
            response = enhanced_audience_coach.llm_client.generate_response(
                smart_prompt
            )
            if response and len(response) > 10:
                ai_msg = response
                st.last_question = None
    except Exception as e:
        logger.error(f"Ollama 生成回應失敗: {e}")
        # 如果 Ollama 失敗，使用備用邏輯

    # Micro-Coach 生成（對話感）
    if not ai_msg:
        prompt = build_micro_prompt(
            {"messages": st.messages, "project_data": st.project_data}, user_text
        )
        raw = enhanced_audience_coach.llm_client.generate_response(prompt)

        ai_msg, quick, state_json = parse_micro_reply(raw)

        # 兜底：如果模型沒給選項，就用舊的缺口型選項
        if not quick:
            quick = generate_enhanced_audience_quick_replies(
                *_calc_audience_coach_completeness(st.project_data)
            )

        # 更新已知（僅用模型聲明的 known_delta，不寫死高層）
        kd = state_json.get("known_delta") or {}
        for k, v in kd.items():
            if v and isinstance(v, str):
                st.project_data[k] = v.strip()

        st.messages.append({"role": "assistant", "content": ai_msg})

        return AudienceCoachChatOut(
            message=ai_msg,
            next_question=None,  # 由 ai_msg 直接呈現問題
            quick_replies=quick,
            project_data=st.project_data,
            completeness_score=state_json.get("completeness")
            or _calc_audience_coach_completeness(st.project_data)[0],
            missing_keys=state_json.get("missing_top")
            or _calc_audience_coach_completeness(st.project_data)[1],
        )

    # 如果 Ollama 有生成回應，使用原有邏輯
    quick = generate_enhanced_audience_quick_replies(score, missing, st.project_data)

    # 記錄 AI 訊息
    st.messages.append({"role": "assistant", "content": ai_msg})

    return AudienceCoachChatOut(
        message=ai_msg,
        next_question=st.last_question,
        quick_replies=quick,
        project_data=st.project_data,
        completeness_score=score,
        missing_keys=missing,
    )


# 新增受眾洞察分析端點
@app.post("/audience-coach/insights")
def get_audience_insights(session_id: str = Body("default")):
    """獲取受眾洞察分析"""
    try:
        st = get_audience_coach_state(session_id)
        insights = enhanced_audience_coach.generate_audience_insights(st.project_data)
        return {"success": True, "insights": insights, "project_data": st.project_data}
    except Exception as e:
        logger.error(f"獲取受眾洞察失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取受眾洞察失敗: {str(e)}")


# 新增受眾策略建議端點
@app.post("/audience-coach/strategy")
def get_audience_strategy(session_id: str = Body("default")):
    """獲取受眾策略建議"""
    try:
        st = get_audience_coach_state(session_id)
        strategy = enhanced_audience_coach.generate_audience_strategy(st.project_data)
        return {"success": True, "strategy": strategy, "project_data": st.project_data}
    except Exception as e:
        logger.error(f"獲取受眾策略失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取受眾策略失敗: {str(e)}")


# 新增受眾教練到企劃專案轉換端點
@app.post("/audience-coach/convert-to-project")
def convert_audience_coach_to_project(session_id: str = Body("default")):
    """將受眾教練會話轉換為企劃專案"""
    try:
        st = get_audience_coach_state(session_id)

        # 轉換資料格式
        converted_data = {
            "project_attributes": {
                "industry": st.project_data.get("project_attributes", {}).get(
                    "industry"
                ),
                "campaign": st.project_data.get("project_attributes", {}).get(
                    "campaign"
                ),
                "is_urgent": None,
            },
            "time_budget": {
                "planning_due_date": st.project_data.get("time_budget", {}).get(
                    "planning_due_date"
                ),
                "campaign_start_date": st.project_data.get("time_budget", {}).get(
                    "campaign_start_date"
                ),
                "campaign_end_date": st.project_data.get("time_budget", {}).get(
                    "campaign_end_date"
                ),
                "budget": st.project_data.get("time_budget", {}).get("budget"),
            },
            "content_strategy": {
                "planning_types": st.project_data.get("content_strategy", {}).get(
                    "planning_types", []
                ),
                "media_formats": st.project_data.get("content_strategy", {}).get(
                    "media_formats", []
                ),
                "audience_lock": st.project_data.get("content_strategy", {}).get(
                    "audience_lock"
                ),
                "audience_behavior": str(
                    st.project_data.get("content_strategy", {}).get(
                        "audience_behavior", {}
                    )
                ),
                "client_materials": None,
                "client_requests": None,
            },
            "technical_needs": {"technical_needs": None},
        }

        # 使用 PlanningAgent 創建企劃專案
        planning_agent = PlanningAgent()
        planning_project = planning_agent.create_planning_project(
            converted_data, f"audience_coach_{session_id}", "受眾教練轉換"
        )

        # 儲存到 Chroma
        chroma_result = planning_agent.save_to_chroma(planning_project)

        return {
            "success": True,
            "planning_project": planning_project.dict(),
            "chroma_result": chroma_result.dict(),
            "message": "成功轉換為企劃專案",
        }

    except Exception as e:
        logger.error(f"轉換企劃專案失敗: {e}")
        raise HTTPException(status_code=500, detail=f"轉換企劃專案失敗: {str(e)}")


# =============================
# 整合對話式企劃需求助手端點
# =============================

# 對話式會話儲存
CHAT_SESSIONS: Dict[str, Any] = {}


class ChatMessage(BaseModel):
    """對話訊息輸入模型"""

    message: str = ""
    user_id: str = "guest"
    session_id: Optional[str] = None


class ChatTurnResponse(BaseModel):
    """對話回應模型"""

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


def _compose_enhanced_requirement(original: str, answers: List[str]) -> str:
    """組合增強的需求描述"""
    if not answers:
        return original
    return f"{original}\n\n補充資訊：\n" + "\n".join(f"- {ans}" for ans in answers)


def _update_project_data_from_answers(
    project_data: Dict[str, Any], answers: List[str]
) -> Dict[str, Any]:
    """基於用戶回答更新專案資料"""
    # 這裡可以實現更智能的資料更新邏輯
    return project_data


def generate_quick_replies(
    completeness_score: float, missing_keys: List[str]
) -> List[str]:
    """生成快速回覆選項"""
    if completeness_score < 0.5:
        return ["我想先了解基本資訊", "請幫我分析需求完整性", "我需要範例參考"]
    elif completeness_score < 0.8:
        return ["繼續補充細節", "我想看看目前的提案", "幫我檢查還缺什麼"]
    else:
        return ["完成需求彙整", "產出最終提案", "儲存到專案池"]


@app.post("/chat/message", response_model=ChatTurnResponse)
def chat_message(payload: ChatMessage):
    """主要的對話端點，處理用戶訊息並返回回應"""
    try:
        planning_agent = PlanningAgent()

        # 創建或獲取會話
        if payload.session_id and payload.session_id in CHAT_SESSIONS:
            sess = CHAT_SESSIONS[payload.session_id]
            is_new = False
        else:
            sess = {
                "session_id": str(uuid.uuid4())[:8],
                "user_id": payload.user_id,
                "original_requirement": (payload.message or "").strip(),
                "answers": [],
                "asked_questions": [],
                "missing_keys": [],
                "completeness_score": 0.0,
                "has_pending_confirmation": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            CHAT_SESSIONS[sess["session_id"]] = sess
            is_new = True

        # 準備文字並更新回答
        if not is_new and payload.message.strip():
            sess["answers"].append(payload.message.strip())

        enhanced = (
            sess["original_requirement"]
            if is_new
            else _compose_enhanced_requirement(
                sess["original_requirement"], sess["answers"]
            )
        )

        # 總是重新計算完整性
        project_data = planning_agent.extract_project_data(enhanced)

        # 智能更新專案資料（基於用戶回答）
        if not is_new and sess["answers"]:
            project_data = _update_project_data_from_answers(
                project_data, sess["answers"]
            )

        comp = planning_agent.compute_completeness(project_data)
        pending = (
            comp.get("pending_confirmation_fields")
            or comp.get("missing_required_keys")
            or comp.get("missing_fields")
            or comp.get("missing_elements")
            or []
        )

        sess["missing_keys"] = pending
        sess["completeness_score"] = float(comp.get("completeness_score", 0.0))
        sess["has_pending_confirmation"] = bool(comp.get("has_pending_confirmation"))
        sess["updated_at"] = datetime.now().isoformat()

        # 總是產生草稿
        planning_project = planning_agent.create_planning_project(
            project_data, sess["user_id"], enhanced
        )
        proposal_text = planning_agent.render_proposal_text(planning_project)
        sess["planning_project"] = planning_project.dict()
        sess["proposal_text"] = proposal_text

        need_more = (
            (comp.get("tool_action") == "ask_clarification")
            or sess["has_pending_confirmation"]
            or sess["completeness_score"] < 0.85  # 使用統一的閾值
        )

        if need_more:
            gqs = group_questions_from_pending(pending)
            raw_qs = (
                planning_agent.generate_project_clarification_questions(
                    enhanced, project_data, comp
                )
                or []
            )
            qs = gqs or raw_qs or ["請描述此專案的產業類別與主要目標受眾"]
            next_q = next((q for q in qs if q not in sess["asked_questions"]), qs[0])
            sess["last_question"] = next_q
            sess["asked_questions"].append(next_q)

            quick_replies = generate_quick_replies(
                sess["completeness_score"], sess["missing_keys"]
            )

            return ChatTurnResponse(
                session_id=sess["session_id"],
                role="assistant",
                message=next_q,
                status="需要澄清",
                completeness_score=sess["completeness_score"],
                missing_keys=sess["missing_keys"],
                asked_questions=sess["asked_questions"],
                next_question=sess["last_question"],
                planning_project=sess["planning_project"],
                proposal_text=sess["proposal_text"],
                quick_replies=quick_replies,
            )

        return ChatTurnResponse(
            session_id=sess["session_id"],
            role="assistant",
            message="需求收集完成！我可以為您產出最終提案或儲存到專案池。",
            status="完成",
            completeness_score=sess["completeness_score"],
            missing_keys=sess["missing_keys"],
            asked_questions=sess["asked_questions"],
            next_question=None,
            planning_project=sess["planning_project"],
            proposal_text=sess["proposal_text"],
            quick_replies=["產出最終提案", "儲存到專案池", "開始新會話"],
        )

    except Exception as e:
        logger.error(f"對話處理失敗: {e}")
        raise HTTPException(status_code=500, detail=f"對話處理失敗: {str(e)}")


@app.post("/chat/autofill", response_model=ChatTurnResponse)
def chat_autofill(payload: ChatMessage):
    """AI 自動補全缺漏欄位"""
    try:
        if not payload.session_id or payload.session_id not in CHAT_SESSIONS:
            raise HTTPException(status_code=400, detail="會話不存在")

        sess = CHAT_SESSIONS[payload.session_id]
        planning_agent = PlanningAgent()

        # 使用 AI 自動補全
        enhanced_requirement = _compose_enhanced_requirement(
            sess["original_requirement"], sess["answers"]
        )

        # 嘗試自動補全
        try:
            # 這裡可以調用 Ollama 進行智能補全
            # 暫時使用基本邏輯
            project_data = planning_agent.extract_project_data(enhanced_requirement)
            comp = planning_agent.compute_completeness(project_data)

            if comp.get("completeness_score", 0) > 0.8:
                # 如果完成度夠高，生成提案
                planning_project = planning_agent.create_planning_project(
                    project_data, sess["user_id"], enhanced_requirement
                )
                proposal_text = planning_agent.render_proposal_text(planning_project)

                sess["planning_project"] = planning_project.dict()
                sess["proposal_text"] = proposal_text
                sess["completeness_score"] = float(comp.get("completeness_score", 0.0))
                sess["updated_at"] = datetime.now().isoformat()

                return ChatTurnResponse(
                    session_id=sess["session_id"],
                    role="assistant",
                    message="AI 自動補全完成！已生成初步提案。",
                    status="自動補全完成",
                    completeness_score=sess["completeness_score"],
                    missing_keys=[],
                    asked_questions=sess["asked_questions"],
                    next_question=None,
                    planning_project=sess["planning_project"],
                    proposal_text=sess["proposal_text"],
                    quick_replies=["查看提案", "繼續完善", "儲存到專案池"],
                )
            else:
                return ChatTurnResponse(
                    session_id=sess["session_id"],
                    role="assistant",
                    message="資訊不足，無法自動補全。請繼續回答問題。",
                    status="需要更多資訊",
                    completeness_score=sess["completeness_score"],
                    missing_keys=comp.get("pending_confirmation_fields", []),
                    asked_questions=sess["asked_questions"],
                    next_question=sess.get("last_question"),
                    planning_project=sess.get("planning_project"),
                    proposal_text=sess.get("proposal_text"),
                    quick_replies=["繼續回答", "查看進度", "重新開始"],
                )

        except Exception as e:
            logger.error(f"AI 自動補全失敗: {e}")
            return ChatTurnResponse(
                session_id=sess["session_id"],
                role="assistant",
                message="自動補全失敗，請手動回答問題。",
                status="自動補全失敗",
                completeness_score=sess["completeness_score"],
                missing_keys=sess["missing_keys"],
                asked_questions=sess["asked_questions"],
                next_question=sess.get("last_question"),
                planning_project=sess.get("planning_project"),
                proposal_text=sess.get("proposal_text"),
                quick_replies=["繼續回答", "查看進度", "重新開始"],
            )

    except Exception as e:
        logger.error(f"自動補全處理失敗: {e}")
        raise HTTPException(status_code=500, detail=f"自動補全處理失敗: {str(e)}")


@app.get("/chat/sessions")
def list_chat_sessions():
    """獲取所有對話會話列表"""
    sessions = []
    for session_id, sess in CHAT_SESSIONS.items():
        sessions.append(
            {
                "session_id": session_id,
                "user_id": sess["user_id"],
                "original_requirement": sess["original_requirement"],
                "completeness_score": sess["completeness_score"],
                "created_at": sess["created_at"],
                "updated_at": sess["updated_at"],
            }
        )
    return {"sessions": sessions}


@app.get("/chat/sessions/{session_id}")
def get_chat_session(session_id: str):
    """獲取特定對話會話詳情"""
    if session_id not in CHAT_SESSIONS:
        raise HTTPException(status_code=404, detail="會話不存在")
    return CHAT_SESSIONS[session_id]


@app.delete("/chat/sessions/{session_id}")
def delete_chat_session(session_id: str):
    """刪除對話會話"""
    if session_id not in CHAT_SESSIONS:
        raise HTTPException(status_code=404, detail="會話不存在")
    del CHAT_SESSIONS[session_id]
    return {"message": "會話已刪除"}


# =============================
# 開放域抽取器
# =============================

OPEN_FIELDS = [
    "project.industry",
    "project.theme",
    "objective",
    "kpi",
    "audience.demographic",
    "audience.scenario",
    "audience.lock",
    "audience.interest",
    "media.formats",
    "media.platforms",
    "time.start",
    "time.end",
    "budget.total",
    "geo",
    "offer",
]


def build_open_extractor_prompt(user_text: str, known: Dict[str, Any]) -> str:
    """
    要求 Gemma 回『單一 JSON』，開放域抽取；高層欄位一律列為 candidates，除非使用者明確肯定。
    """
    return f"""
你是資訊抽取器。從使用者的自然語句抽出與行銷企劃相關的欄位，**不得杜撰**。
請只輸出一個 JSON 物件，不要多餘文字。

欄位集合（可缺省）：{OPEN_FIELDS}

輸出 JSON 結構：
{{
  "known_delta": {{}},             // 本回合可直接確定的欄位（低風險）
  "candidates": {{}},              // 需確認的高層候選（如 industry/theme/geo/brand）
  "entities": [                    // 句中抓到的關鍵實體（完全開放域）
    {{"text":"", "type":"", "role":""}}  // type 例如 product/service/species/event/brand/location/persona…
  ],
  "intent": "awareness|acquisition|conversion|retention|unknown",
  "theme_suggestions": [],         // 2~4 個主題方向（若可推論）
  "audience_options": [],          // 2~5 個受眾片語（開放域）
  "kpi_options": [],               // 2~4 個 KPI 候選（依 intent 合理）
  "period_hint": "",               // 例如 "活動期間 2025/09/15 至 2025/10/31"
  "confidence": 0.0                // 0~1 總體信心
}}

抽取規則：
- 不要把使用者整句原封丟入欄位；要正規化（日期 YYYY/MM/DD，金額整數元）。
- 高層欄位（project.industry, project.theme, geo, brand）預設放入 candidates，不直接進 known_delta。
- 若語句包含具體主題/明星元素（任何領域都可），回傳 2~4 個「可作為 campaign 主題」的簡短選項。
- KPI 依 intent 合理化：awareness→曝光/到站、acquisition→表單/安裝、conversion→成交/ROAS、retention→回購/活躍。
- 產業必須是開放文字（可為「動物園」「手搖飲」「B2B SaaS 供應商」等），不可侷限白名單。
- 若資訊不足，留空；不要亂猜。

已知（可參考但不可覆寫）：{json.dumps({k:v for k,v in (known or {}).items() if v}, ensure_ascii=False)}

使用者句子：{user_text}
只輸出 JSON。""".strip()


def llm_open_extract(user_text: str, known: Dict[str, Any]) -> Dict[str, Any]:
    """使用 LLM 進行開放域資訊抽取"""
    import re
    import json

    # LLMClient 在 app.py 中定義，直接使用
    prompt = build_open_extractor_prompt(user_text, known)
    llm_client = LLMClient()
    raw = llm_client.generate_response(prompt, model="gpt-oss:20b")
    m = re.search(r"\{.*\}", raw, re.S)
    data = json.loads(m.group(0)) if m else {}

    # 兜底保護
    for k in [
        "known_delta",
        "candidates",
        "entities",
        "theme_suggestions",
        "audience_options",
        "kpi_options",
    ]:
        data.setdefault(k, [] if k.endswith("_options") or k == "entities" else {})
    data.setdefault("period_hint", "")
    data.setdefault("intent", "unknown")
    data.setdefault("confidence", 0.0)
    return data


def open_build_actions(
    ext: Dict[str, Any], known: Dict[str, Any]
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    基於開放域抽取結果，生成自然句與動態動作按鈕
    返回：(教練文字, 動作按鈕列表)
    """
    coach_text = ""
    actions = []

    # 1. 處理高層候選（需要確認）
    candidates = ext.get("candidates", {})
    if candidates:
        coach_text += "我注意到您提到了以下資訊，請確認：\n"
        for field, value in candidates.items():
            if field == "project.industry":
                coach_text += f"• 產業：{value}\n"
            elif field == "project.theme":
                coach_text += f"• 主題：{value}\n"
            elif field == "geo":
                coach_text += f"• 地理範圍：{value}\n"
            elif field == "brand":
                coach_text += f"• 品牌：{value}\n"

            # 為每個候選生成確認動作
            actions.append(
                {
                    "type": "confirm",
                    "field": field,
                    "value": value,
                    "text": f"確認 {field}: {value}",
                    "action": "confirm_field",
                }
            )

    # 2. 處理主題建議
    theme_suggestions = ext.get("theme_suggestions", [])
    if theme_suggestions:
        if not coach_text:
            coach_text += "基於您的描述，我建議以下主題方向：\n"
        else:
            coach_text += "\n主題建議：\n"

        for theme in theme_suggestions:
            coach_text += f"• {theme}\n"
            actions.append(
                {
                    "type": "select_theme",
                    "value": theme,
                    "text": f"選擇主題：{theme}",
                    "action": "select_theme",
                }
            )

    # 3. 處理受眾選項
    audience_options = ext.get("audience_options", [])
    if audience_options:
        if not coach_text:
            coach_text += "受眾分析建議：\n"
        else:
            coach_text += "\n受眾選項：\n"

        for audience in audience_options:
            coach_text += f"• {audience}\n"
            actions.append(
                {
                    "type": "select_audience",
                    "value": audience,
                    "text": f"選擇受眾：{audience}",
                    "action": "select_audience",
                }
            )

    # 4. 處理 KPI 選項
    kpi_options = ext.get("kpi_options", [])
    if kpi_options:
        if not coach_text:
            coach_text += "KPI 建議：\n"
        else:
            coach_text += "\nKPI 選項：\n"

        for kpi in kpi_options:
            coach_text += f"• {kpi}\n"
            actions.append(
                {
                    "type": "select_kpi",
                    "value": kpi,
                    "text": f"選擇 KPI：{kpi}",
                    "action": "select_kpi",
                }
            )

    # 5. 處理期間提示
    period_hint = ext.get("period_hint", "")
    if period_hint:
        if not coach_text:
            coach_text += "時間資訊：\n"
        else:
            coach_text += "\n時間資訊：\n"
        coach_text += f"• {period_hint}\n"

    # 6. 如果沒有特定內容，提供通用引導
    if not coach_text:
        intent = ext.get("intent", "unknown")
        if intent == "awareness":
            coach_text = "看起來您希望提升品牌知名度，讓我們一起規劃曝光策略。"
        elif intent == "acquisition":
            coach_text = "您的目標是獲取新客戶，我們可以設計吸引潛在客戶的活動。"
        elif intent == "conversion":
            coach_text = "轉換率提升是關鍵，讓我們優化轉換漏斗。"
        elif intent == "retention":
            coach_text = "客戶留存很重要，我們可以設計忠誠度計劃。"
        else:
            coach_text = "請告訴我更多關於您的行銷目標，我會協助您規劃。"

    # 7. 添加通用動作
    actions.extend(
        [
            {"type": "general", "text": "提供更多資訊", "action": "provide_more_info"},
            {"type": "general", "text": "查看進度", "action": "check_progress"},
        ]
    )

    return coach_text, actions


# =============================
# 回合控制器補丁
# =============================

# 1) 欄位優先序
SLOT_ORDER = [
    "project.industry",
    "objective",
    "kpi",
    "audience.demographic",
    "audience.scenario",
    "audience.lock",
    "media.formats",
    "media.platforms",
    "time.start",
    "time.end",
    "budget.total",
]

# 2) 產業情境的 option bank，僅示例，先放幾個夠用的
DOMAIN = {
    "觀光場館": {
        "audience.demographic": [
            "家庭 親子",
            "校園 6到12歲",
            "情侶 約會",
            "外地觀光客",
            "在地居民",
        ],
        "audience.scenario": [
            "觀看票價頁超過30秒",
            "查詢交通與園區地圖",
            "加入收藏或願望清單",
            "觀看動物直播超過1分鐘",
        ],
        "media.formats": ["短影音", "社群貼文", "KOL 親子開箱", "聯播網橫幅"],
    },
    "_default": {
        "audience.demographic": ["男25至44 上班族", "女25至34 上班族", "學生大專院校"],
        "audience.scenario": [
            "加到購物車未結帳",
            "觀看產品頁超過30秒",
            "搜尋品牌關鍵字",
        ],
        "media.formats": ["短影音", "社群貼文", "聯播網橫幅"],
    },
}


def pick_next_slot(known: dict) -> str:
    """選擇下一個要填寫的欄位"""
    for k in SLOT_ORDER:
        if not known.get(k):
            return k
    return None


def current_frame(known: dict) -> dict:
    """將產業對齊到預設模板"""
    # 將「動物園」對齊為「觀光場館」這一類模板
    industry = known.get("project.industry")
    if industry in ["動物園", "水族館", "旅遊觀光", "觀光場館"]:
        frame_industry = "觀光場館"
    else:
        frame_industry = industry or None
    return {"industry": frame_industry}


def get_slot_options(slot: str, frame: dict) -> List[str]:
    """根據當前欄位和產業框架，提供選項建議，嚴格來自對應的 domain"""
    industry = frame.get("industry")
    domain = DOMAIN.get(industry, DOMAIN["_default"])

    # 根據欄位類型提供選項，嚴格來自 domain
    if slot == "audience.demographic":
        options = domain.get("audience.demographic", [])
        # 如果沒有產業框架，加入通用選項
        if not industry:
            options.extend(["男25至44 上班族", "女25至34 上班族", "學生大專院校"])
        return options
    elif slot == "audience.scenario":
        options = domain.get("audience.scenario", [])
        # 如果沒有產業框架，加入通用選項
        if not industry:
            options.extend(["加到購物車未結帳", "觀看產品頁超過30秒", "搜尋品牌關鍵字"])
        return options
    elif slot == "media.formats":
        options = domain.get("media.formats", [])
        # 如果沒有產業框架，加入通用選項
        if not industry:
            options.extend(["短影音", "社群貼文", "聯播網橫幅"])
        return options
    elif slot == "project.industry":
        # 產業選項不依賴框架，提供完整選項
        return [
            "消費品",
            "科技業",
            "金融業",
            "服務業",
            "觀光場館",
            "教育",
            "醫療",
            "其他",
        ]
    elif slot == "objective":
        # 目標選項不依賴框架
        return ["品牌知名度", "產品銷售", "用戶註冊", "活動參與", "客戶服務", "其他"]
    elif slot == "kpi":
        # KPI選項不依賴框架
        return ["點擊率", "轉換率", "曝光量", "互動率", "銷售額", "其他"]
    elif slot == "time.start":
        # 時間選項不依賴框架
        return ["下個月", "下季", "年中", "年底", "其他"]
    elif slot == "time.end":
        # 時間選項不依賴框架
        return ["一個月後", "一季後", "半年後", "一年後", "其他"]
    elif slot == "budget.total":
        # 預算選項不依賴框架
        return ["10萬以下", "10-50萬", "50-100萬", "100-500萬", "500萬以上"]

    return []


def normalize_slot_value(slot: str, value: str) -> str:
    """正規化欄位值"""
    if slot == "time.start" or slot == "time.end":
        # 日期正規化
        if "下個月" in value:
            return "2024/02/01"
        elif "下季" in value:
            return "2024/04/01"
        elif "年中" in value:
            return "2024/06/01"
        elif "年底" in value:
            return "2024/12/01"
        # 可以添加更多日期正規化邏輯
        return value
    elif slot == "budget.total":
        # 預算正規化
        if "萬" in value:
            # 提取數字並轉換為整數
            import re

            match = re.search(r"(\d+)", value)
            if match:
                num = int(match.group(1))
                if "以下" in value:
                    return f"{num*10000}"
                elif "以上" in value:
                    return f"{num*10000}"
                else:
                    return f"{num*10000}"
        return value

    return value


# =============================
# 微回合解析函数
# =============================


def parse_micro_reply(text: str) -> Tuple[str, List[str], Dict[str, Any]]:
    """解析微回合回复，提取可见区和STATE，並正規化欄位值"""
    import re

    # 取四行可见区
    tip = re.search(r"提示：(.+)", text)
    q = re.search(r"問題：(.+)", text)
    copy_text = re.search(r"可複製句：(.+)", text)
    opts = re.search(r"選項：(.+)", text)

    # 解析 quick replies
    quick = []
    if opts:
        quick = [s.strip() for s in opts.group(1).split("｜") if s.strip()]

    # 合成 message（只显示提示＋问题）
    msg = ""
    if tip:
        msg += tip.group(1).strip() + "\n"
    if q:
        msg += q.group(1).strip()

    # 解析 STATE
    st_match = re.search(r"<STATE>\s*(\{.*\})\s*</STATE>", text, re.S)
    state_json = {}
    if st_match:
        try:
            state_json = json.loads(st_match.group(1))

            # 正規化 known_delta 中的欄位值
            if "known_delta" in state_json:
                normalized_delta = {}
                for slot, value in state_json["known_delta"].items():
                    if isinstance(value, str) and value.strip():
                        normalized_value = normalize_slot_value(slot, value.strip())
                        normalized_delta[slot] = normalized_value
                state_json["known_delta"] = normalized_delta

        except Exception:
            state_json = {}

    return msg.strip(), quick, state_json


def build_micro_prompt(state: Dict[str, Any], user_text: str) -> str:
    """构建微回合提示词，整合回合控制器"""
    # 只带必要上下文，避免模型话多
    hist = state.get("messages", [])[-6:]
    htxt = "\n".join([f"{m['role']}：{m['content']}" for m in hist])
    known = state.get("project_data", {})
    score, missing = _calc_audience_coach_completeness(known)

    # 回合控制器：選擇下一個目標欄位
    next_slot = pick_next_slot(known)
    frame = current_frame(known)
    slot_options = get_slot_options(next_slot, frame) if next_slot else []

    # 構建針對性的提示詞
    slot_instruction = ""
    if next_slot:
        slot_instruction = f"\n【本回合目標欄位：{next_slot}】\n"
        if slot_options:
            slot_instruction += f"【建議選項】{'｜'.join(slot_options)}\n"

    # 微回合教練系統提示
    micro_coach_system = (
        "【角色】\n"
        "你是廣告企劃教練，採微回合。每回合只推進一格。\n\n"
        "【本輪目標】\n"
        "GOAL_SLOT = <由系統提供，例如 audience.demographic>\n"
        'FRAME = {"industry":"觀光場館" 或 null}\n\n'
        "【輸出規格，嚴格遵守，且不可多字】\n"
        "提示：≤25字，先一句白話解釋為何本題重要\n"
        "問題：只問一件事，專注於收集資訊，不要列出選項\n"
        "注意：不要輸出選項列表，選項會由前端動態顯示\n\n"
        "<STATE>\n"
        '{"known_delta":{本回合新確定欄位},"missing_top":[最多5個],"next_intent":"ask|draft","completeness":0~1}\n'
        "</STATE>\n\n"
        "【名詞解釋規則】\n"
        "只解釋本題唯一名詞，先解釋再提問，例如「家庭＝含孩童的家戶，常見親子出遊」。\n\n"
        "【一致性與上下文】\n"
        "若你的建議不在 domain，先反問「是否換案子」，並在選項加入「開新案」而不亂跳。\n"
        "高層欄位只在使用者明確同意或連續兩回合一致時，才寫入 known_delta。\n\n"
        "【正規化】\n"
        "日期 YYYY/MM/DD。金額整數元。不得把使用者整句原樣塞欄位。"
    )

    return micro_coach_system + "\n\n" + user_prefix


# 智能選項管理器 - 負責智能選擇和生成相關選項
class SmartOptionManager:
    """智能選項管理器，根據當前對話狀態和缺失欄位智能選擇相關選項"""

    def __init__(self):
        self.predefined_options = PREDEFINED_OPTIONS
        self.option_rules = OPTION_SELECTION_RULES
        self.quick_reply_templates = QUICK_REPLY_TEMPLATES

    def get_contextual_options(
        self, missing_keys: List[str], project_data: Dict[str, Any] = None
    ) -> List[str]:
        """根據缺失欄位和專案資料生成上下文相關的選項"""
        contextual_options = []

        # 為每個缺失欄位生成相關選項
        for missing_key in missing_keys[:5]:  # 最多處理5個缺失欄位
            if missing_key in self.option_rules:
                rule = self.option_rules[missing_key]
                option_category = rule["options"]
                max_count = rule["max_count"]

                if option_category in self.predefined_options:
                    # 從預定義選項中選擇
                    options = self.predefined_options[option_category]

                    # 根據專案資料智能過濾選項（如果有的話）
                    if project_data:
                        filtered_options = self._filter_options_by_context(
                            options, missing_key, project_data
                        )
                        selected_options = filtered_options[:max_count]
                    else:
                        selected_options = options[:max_count]

                    # 只添加選項，不添加描述標記
                    contextual_options.extend(selected_options)

        return contextual_options

    def _filter_options_by_context(
        self, options: List[str], missing_key: str, project_data: Dict[str, Any]
    ) -> List[str]:
        """根據專案資料上下文過濾選項"""
        # 這裡可以實現更複雜的邏輯，比如根據產業過濾受眾選項
        # 目前先返回原始選項，後續可以擴展
        return options

    def get_smart_quick_replies(
        self,
        completeness_score: float,
        missing_keys: List[str],
        project_data: Dict[str, Any] = None,
    ) -> List[str]:
        """生成智能快速回覆，結合預定義模板和上下文選項"""
        quick_replies = []

        # 1. 根據完整性分數選擇基礎模板
        if completeness_score < 0.3:
            template_key = "initial"
        elif completeness_score < 0.7:
            template_key = "progress"
        elif completeness_score < 0.9:
            template_key = "advanced"
        else:
            template_key = "completion"

        # 2. 添加基礎快速回覆
        base_replies = self.quick_reply_templates.get(template_key, [])
        quick_replies.extend(base_replies[:3])  # 最多3個基礎回覆

        # 3. 添加上下文相關選項
        if missing_keys:
            contextual_options = self.get_contextual_options(missing_keys, project_data)
            quick_replies.extend(contextual_options)

        # 4. 確保總數不超過8個選項
        return quick_replies[:8]

    def get_field_specific_options(
        self, field_key: str, max_count: int = 5
    ) -> List[str]:
        """獲取特定欄位的預定義選項"""
        if field_key in self.option_rules:
            rule = self.option_rules[field_key]
            option_category = rule["options"]
            max_count = min(max_count, rule["max_count"])

            if option_category in self.predefined_options:
                return self.predefined_options[option_category][:max_count]

        return []

    def generate_question_with_options(
        self, field_key: str, project_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """生成帶有預定義選項的問題"""
        if field_key in self.option_rules:
            rule = self.option_rules[field_key]
            options = self.get_field_specific_options(field_key)

            return {
                "question": rule["description"],
                "options": options,
                "field_key": field_key,
                "max_count": rule["max_count"],
            }

        return None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=FASTAPI_HOST, port=FASTAPI_PORT, reload=True)
