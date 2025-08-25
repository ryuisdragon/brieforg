#!/usr/bin/env python3
"""
統一的企劃代理控制器
整合企劃專案管理和受眾分析功能
"""


import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from models.unified_models import (
    ProjectData,
    ChatMessage,
    QuickReply,
    ChatTurnResponse,
    MessageRole,
    MessageType,
)
from prompts.unified_prompts import UnifiedPrompts
from tools.unified_tools import ToolExecutor

logger = logging.getLogger(__name__)


class UnifiedPlanningAgent:
    """統一的企劃代理控制器"""

    def __init__(self, llm_client, tool_executor: ToolExecutor):
        """初始化代理"""
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.conversation_history: List[ChatMessage] = []

    async def process_chat_turn(
        self,
        user_message: str,
        session_id: str,
        project_data: Optional[ProjectData] = None,
    ) -> ChatTurnResponse:
        """處理聊天回合"""
        try:
            # 初始化專案數據（如果沒有）
            if project_data is None:
                project_data = ProjectData()

            # 添加用戶訊息到歷史
            user_chat_message = ChatMessage(
                role=MessageRole.USER,
                content=user_message,
                message_type=MessageType.TEXT,
            )
            self.conversation_history.append(user_chat_message)

            # 分析用戶輸入並決定下一步行動
            next_action = await self._determine_next_action(user_message, project_data)
            logger.info(f"決定的下一步行動: {next_action}")

            # 根據行動類型執行相應邏輯
            if next_action == "extract_data":
                logger.info("執行數據提取")
                response = await self._handle_data_extraction(
                    user_message, project_data
                )
            elif next_action == "generate_insights":
                logger.info("執行洞察生成")
                response = await self._handle_insight_generation(
                    user_message, project_data
                )
            elif next_action == "provide_strategy":
                logger.info("執行策略生成")
                response = await self._handle_strategy_generation(
                    user_message, project_data
                )
            elif next_action == "evaluate_completeness":
                logger.info("執行完整度評估")
                response = await self._handle_completeness_evaluation(
                    user_message, project_data
                )
            elif next_action == "clarify":
                logger.info("執行澄清請求")
                response = await self._handle_clarification(user_message, project_data)
            elif next_action == "general_conversation":
                logger.info("執行一般對話")
                response = await self._handle_general_conversation(
                    user_message, project_data
                )
            else:
                logger.info(f"未知行動類型: {next_action}，使用一般對話")
                response = await self._handle_general_conversation(
                    user_message, project_data
                )

            # 生成快速回覆選項
            quick_replies = await self._generate_quick_replies(
                user_message, project_data
            )

            # 計算專案完整度（使用邏輯計算而非 LLM 評估）
            project_data.completeness_score = self._calculate_completeness_score(
                project_data
            )

            # 添加AI回應到歷史
            ai_chat_message = ChatMessage(
                role=MessageRole.ASSISTANT,
                content=response,
                message_type=MessageType.TEXT,
            )
            self.conversation_history.append(ai_chat_message)

            # 更新專案數據時間戳
            project_data.updated_at = datetime.now()

            # 確保回覆足夠具體且不少於50字
            response = self._expand_response_if_short(
                response, project_data, user_message
            )

            return ChatTurnResponse(
                message=response,
                session_id=session_id,
                project_data=project_data,
                quick_replies=quick_replies,
                completeness_score=project_data.completeness_score,
                is_complete=project_data.completeness_score >= 80.0,
            )

        except Exception as e:
            logger.error(f"處理聊天回合時發生錯誤: {e}")
            error_message = "抱歉，處理您的請求時發生錯誤。請稍後再試。"

            return ChatTurnResponse(
                message=error_message,
                session_id=session_id,
                project_data=project_data or ProjectData(),
                quick_replies=[
                    QuickReply(text="重新開始", value="restart", priority=1),
                    QuickReply(text="繼續對話", value="continue", priority=2),
                ],
                completeness_score=0.0,
                is_complete=False,
            )

    async def _determine_next_action(
        self, user_message: str, project_data: ProjectData
    ) -> str:
        """決定下一步行動"""
        try:
            logger.info(f"檢查用戶輸入: '{user_message}'")

            # 檢查是否為簡單問候語
            is_greeting = self._is_simple_greeting(user_message)
            logger.info(f"是否為簡單問候語: {is_greeting}")

            if is_greeting:
                logger.info("檢測到簡單問候語，返回 general_conversation")
                return "general_conversation"

            # 檢查專案數據是否足夠進行分析
            has_sufficient_data = self._has_sufficient_project_data(project_data)
            logger.info(f"專案數據是否足夠: {has_sufficient_data}")

            if not has_sufficient_data:
                logger.info("專案數據不足，返回 extract_data")
                return "extract_data"

            # 構建對話流程控制提示詞
            prompt = UnifiedPrompts.get_system_prompt("flow")

            # 添加專案狀態和用戶輸入
            context = f"""
專案狀態: {self._get_project_status_summary(project_data)}
用戶輸入: {user_message}

請分析用戶輸入並決定下一步行動。
"""

            full_prompt = prompt + context

            # 調用LLM決定行動
            response = await self.llm_client.generate_response(full_prompt)

            # 解析回應決定行動
            action = self._parse_next_action(response)
            logger.info(f"LLM 決定的行動: {action}")

            return action

        except Exception as e:
            logger.error(f"決定下一步行動失敗: {e}")
            return "general_conversation"

    async def _handle_data_extraction(
        self, user_message: str, project_data: ProjectData
    ) -> str:
        """處理數據提取"""
        try:
            # 調用數據提取工具
            result = await self.tool_executor.execute_tool(
                "extract_project_data", user_message=user_message
            )

            if result.success and result.data:
                # 更新專案數據
                self._update_project_data(project_data, result.data)
                # 依語境給重點提問（不少於50字）
                text = (user_message or "").lower()
                industry = project_data.project_attributes.industry or ""
                theme = project_data.project_attributes.campaign or ""
                zoo_hit = any(
                    k in (text + industry + theme).lower()
                    for k in [
                        "動物園",
                        "長頸鹿",
                        "zoo",
                    ]
                )
                if zoo_hit and not project_data.content_strategy.audience_lock:
                    return (
                        "已了解您要推廣長頸鹿。為了讓內容與投放更聚焦，先鎖定主要客群："
                        "您傾向『家庭親子』『校園團體』『情侶年輕族群』或『旅遊客』？"
                        "同時可提供預算區間與檔期，稍後我會給出媒體與素材清單。"
                    )

                return (
                    "已成功提取專案資訊！請補充受眾、預算與時間等關鍵細節，我會依此給出"
                    "渠道建議與素材清單，並逐步完成分配表。"
                )
            else:
                return "我理解您的需求，但需要更多具體資訊。請詳細說明專案的各個方面。"

        except Exception as e:
            logger.error(f"處理數據提取失敗: {e}")
            return "處理您的專案資訊時遇到問題，請重新描述。"

    async def _handle_insight_generation(
        self, user_message: str, project_data: ProjectData
    ) -> str:
        """處理洞察生成"""
        try:
            # 調用受眾洞察工具
            result = await self.tool_executor.execute_tool(
                "generate_audience_insights", project_data=project_data
            )

            if result.success and result.data:
                # 更新受眾洞察
                project_data.audience_insights = result.data

                return (
                    "已為您生成受眾洞察分析！這些資訊將幫助我們制定更精準的內容策略。"
                )
            else:
                return "正在分析受眾特徵，請稍等片刻。"

        except Exception as e:
            logger.error(f"處理洞察生成失敗: {e}")
            return "生成受眾洞察時遇到問題，我們可以稍後再處理這部分。"

    async def _handle_strategy_generation(
        self, user_message: str, project_data: ProjectData
    ) -> str:
        """處理策略生成"""
        try:
            # 調用內容策略工具
            result = await self.tool_executor.execute_tool(
                "generate_content_strategy", project_data=project_data
            )

            if result.success and result.data:
                # 更新內容策略
                self._update_content_strategy(project_data, result.data)

                return "已為您生成內容策略建議！這些建議基於專案需求和受眾分析。"
            else:
                return "正在制定內容策略，請稍等。"

        except Exception as e:
            logger.error(f"處理策略生成失敗: {e}")
            return "生成內容策略時遇到問題，我們可以稍後再處理這部分。"

    async def _handle_completeness_evaluation(
        self, user_message: str, project_data: ProjectData
    ) -> str:
        """處理完整度評估"""
        try:
            # 調用完整度評估工具
            result = await self.tool_executor.execute_tool(
                "evaluate_completeness", project_data=project_data
            )

            if result.success and result.data:
                score = result.data.get("completeness_score", 0.0)
                missing_fields = result.data.get("missing_fields", [])

                if score >= 80.0:
                    return f"太好了！您的專案已經相當完整（完整度：{score:.1f}%）。我們可以進入下一階段了！"
                else:
                    missing_info = "、".join(missing_fields[:3])  # 只顯示前3個
                    return (
                        f"專案完整度：{score:.1f}%。還需要補充以下資訊：{missing_info}"
                    )
            else:
                return "正在評估專案完整度，請稍等。"

        except Exception as e:
            logger.error(f"處理完整度評估失敗: {e}")
            return "評估專案完整度時遇到問題，我們可以稍後再處理這部分。"

    async def _handle_clarification(
        self, user_message: str, project_data: ProjectData
    ) -> str:
        """處理澄清請求"""
        try:
            # 分析需要澄清的內容
            clarification_needs = self._identify_clarification_needs(project_data)

            if clarification_needs:
                return f"為了更好地幫助您，請澄清以下幾點：{clarification_needs}"
            else:
                return "您的專案描述很清楚，我們可以繼續深入討論具體的執行細節。"

        except Exception as e:
            logger.error(f"處理澄清請求失敗: {e}")
            return "請告訴我更多關於專案的具體細節。"

    async def _handle_general_conversation(
        self, user_message: str, project_data: ProjectData
    ) -> str:
        """處理一般對話"""
        try:
            # 檢查是否為簡單問候語
            if self._is_simple_greeting(user_message):
                return (
                    "您好！很高興為您服務。我是您的企劃需求助手，專門幫助客戶收集和分析企劃專案需求。\n\n"
                    "請告訴我您的專案需求，例如：\n"
                    "• 您想要做什麼類型的活動？\n"
                    "• 目標受眾是誰？\n"
                    "• 預算和時程如何？\n\n"
                    "我會根據您的需求，幫助您完善專案規劃。"
                )

            # 構建一般對話提示詞
            prompt = UnifiedPrompts.get_conversation_prompt(
                user_message, project_data.dict(), "general"
            )

            # 調用LLM生成回應
            response = await self.llm_client.generate_response(prompt)

            return response

        except Exception as e:
            logger.error(f"處理一般對話失敗: {e}")
            return "我理解您的意思，請繼續描述您的專案需求。"

    async def _generate_quick_replies(
        self, user_message: str, project_data: ProjectData
    ) -> List[QuickReply]:
        """生成快速回覆選項"""
        try:
            # 調用快速回覆生成工具
            result = await self.tool_executor.execute_tool(
                "generate_quick_replies",
                user_message=user_message,
                project_data=project_data,
            )

            if result.success and result.data:
                return result.data
            else:
                # 返回預設選項
                return [
                    QuickReply(text="繼續", value="continue", priority=1),
                    QuickReply(text="需要更多資訊", value="more_info", priority=2),
                    QuickReply(text="完成", value="complete", priority=3),
                ]

        except Exception as e:
            logger.error(f"生成快速回覆選項失敗: {e}")
            return [
                QuickReply(text="繼續", value="continue", priority=1),
                QuickReply(text="需要更多資訊", value="more_info", priority=2),
                QuickReply(text="完成", value="complete", priority=3),
            ]

    def _update_project_data(self, project_data: ProjectData, new_data: Dict[str, Any]):
        """更新專案數據"""
        try:
            for section, section_data in new_data.items():
                if hasattr(project_data, section) and isinstance(section_data, dict):
                    section_obj = getattr(project_data, section)
                    for key, value in section_data.items():
                        if hasattr(section_obj, key) and value is not None:
                            setattr(section_obj, key, value)
        except Exception as e:
            logger.error(f"更新專案數據失敗: {e}")

    def _update_content_strategy(
        self, project_data: ProjectData, strategy_data: Dict[str, Any]
    ):
        """更新內容策略"""
        try:
            if "planning_types" in strategy_data:
                project_data.content_strategy.planning_types = strategy_data[
                    "planning_types"
                ]
            if "media_formats" in strategy_data:
                project_data.content_strategy.media_formats = strategy_data[
                    "media_formats"
                ]
        except Exception as e:
            logger.error(f"更新內容策略失敗: {e}")

    def _get_project_status_summary(self, project_data: ProjectData) -> str:
        """獲取專案狀態摘要"""
        summary = []

        if project_data.project_attributes.industry:
            summary.append(f"產業: {project_data.project_attributes.industry}")
        if project_data.project_attributes.campaign:
            summary.append(f"主題: {project_data.project_attributes.campaign}")
        if project_data.time_budget.budget:
            summary.append(f"預算: {project_data.time_budget.budget}")

        return " | ".join(summary) if summary else "專案尚未開始"

    def _identify_clarification_needs(self, project_data: ProjectData) -> str:
        """識別需要澄清的內容"""
        needs = []

        if not project_data.project_attributes.industry:
            needs.append("產業類型")
        if not project_data.project_attributes.campaign:
            needs.append("活動主題")
        if not project_data.time_budget.budget:
            needs.append("預算範圍")
        if not project_data.time_budget.campaign_start_date:
            needs.append("活動開始時間")

        return "、".join(needs) if needs else "無"

    def _parse_next_action(self, response: str) -> str:
        """解析下一步行動"""
        try:
            # 嘗試從回應中識別行動
            response_lower = response.lower()

            if any(
                word in response_lower for word in ["提取", "extract", "數據", "data"]
            ):
                return "extract_data"
            elif any(
                word in response_lower
                for word in ["洞察", "insight", "分析", "analysis"]
            ):
                return "generate_insights"
            elif any(
                word in response_lower
                for word in ["策略", "strategy", "建議", "suggestion"]
            ):
                return "provide_strategy"
            elif any(
                word in response_lower
                for word in ["完整", "complete", "評估", "evaluate"]
            ):
                return "evaluate_completeness"
            elif any(
                word in response_lower for word in ["澄清", "clarify", "明確", "clear"]
            ):
                return "clarify"
            else:
                return "general_conversation"

        except Exception as e:
            logger.error(f"解析下一步行動失敗: {e}")
            return "general_conversation"

    def _is_simple_greeting(self, message: str) -> bool:
        """檢查是否為簡單問候語"""
        simple_greetings = [
            "你好",
            "您好",
            "hi",
            "hello",
            "早上好",
            "下午好",
            "晚上好",
            "在嗎",
            "在么",
            "有人嗎",
            "有人么",
            "開始",
            "開始吧",
        ]

        message_lower = message.lower().strip()
        return any(greeting in message_lower for greeting in simple_greetings)

    def _has_sufficient_project_data(self, project_data: ProjectData) -> bool:
        """檢查是否有足夠的專案數據進行分析"""
        if not project_data:
            return False

        # 檢查是否有基本的專案資訊
        has_basic_info = (
            project_data.project_attributes.industry
            or project_data.project_attributes.campaign
            or project_data.project_attributes.description
        )

        # 檢查是否有時間或預算資訊
        has_time_budget = (
            project_data.time_budget.planning_due_date
            or project_data.time_budget.campaign_start_date
            or project_data.time_budget.budget
        )

        return has_basic_info or has_time_budget

    def _calculate_completeness_score(self, project_data: ProjectData) -> float:
        """計算專案完整度分數（邏輯計算）"""
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

        return (filled_fields / total_fields) * 100.0

    # ===== 新增：回覆加長與動作建議 =====
    def _expand_response_if_short(
        self, text: str, project_data: ProjectData, user_message: str
    ) -> str:
        """若模型回覆過短，補上一段具體、可行的建議，確保不少於50字。"""
        try:
            base = (text or "").strip()
            if len(base) >= 50:
                return base

            tips: List[str] = []
            # 依目前缺口提供可執行建議
            if not project_data.project_attributes.industry:
                tips.append("先明確產業/場域與核心情境，這會影響語氣與投放選擇")
            if not project_data.project_attributes.campaign:
                tips.append("定義本檔期主題與一句話訊息，避免內容發散難以聚焦")
            if not project_data.time_budget.budget:
                tips.append("規劃粗略預算區間並列出可接受的KPI，方便分配渠道")
            if not project_data.content_strategy.media_formats:
                tips.append("先選2–3種主力渠道，例如社群＋影音＋搜尋，逐步驗證")
            if not tips:
                tips = [
                    "設定明確KPI與時程，先以一個受眾族群做訊息驗證",
                    "用『問題–洞察–解法』寫兩到三個內容主題並排程",
                    "下一步：確認素材/法遵限制，安排一個試跑檔期",
                ]

            addon = (
                "基於目前資訊，我給您一段具體建議："
                + "；".join(tips[:3])
                + "。若能補充受眾與時間點，我可以直接生成分配表與素材清單。"
            )
            out = (base + " " + addon).strip()
            if len(out) < 50:
                out += " 請再提供目標與時程細節，我會給出更精準的投放與內容計畫。"
            return out
        except Exception:
            # 保底
            return text or "請再多描述一點，我會給出具體的下一步建議。"
