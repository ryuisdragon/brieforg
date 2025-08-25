#!/usr/bin/env python3
"""
狀態機硬控流程代理
實現固定的槽位收集流程，替代LLM自選流程
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

from models.state_machine_models import (
    SlotKey,
    ProjectSlots,
    StateMachineOutput,
    SuggestionBubble,
    RationaleCard,
    SLOT_ORDER,
    MEDIA_FORMATS_WHITELIST,
    PLAN_TYPE_OPTIONS,
    is_slot_filled,
    get_next_slot,
    calculate_completion,
    get_missing_keys,
    validate_slot_value,
)
from prompts.state_machine_prompts import StateMachinePrompts

logger = logging.getLogger(__name__)


class StateMachineAgent:
    """狀態機硬控流程代理"""

    def __init__(self, llm_client):
        """初始化代理"""
        self.llm_client = llm_client
        self.prompts = StateMachinePrompts()

    async def process_user_input(
        self, user_message: str, current_slots: ProjectSlots
    ) -> StateMachineOutput:
        """處理用戶輸入並返回狀態機輸出"""
        try:
            # 1. 分析用戶輸入，提取相關槽位信息
            extracted_data = await self._extract_slot_data(user_message, current_slots)

            # 2. 更新槽位數據
            updated_slots = self._update_slots(current_slots, extracted_data)

            # 3. 獲取下一個需要填充的槽位
            next_slot = get_next_slot(updated_slots)

            # 4. 生成回應和建議
            if next_slot == "done":
                return await self._generate_completion_response(updated_slots)
            else:
                return await self._generate_next_slot_response(
                    next_slot, updated_slots, user_message
                )

        except Exception as e:
            logger.error(f"處理用戶輸入失敗: {e}")
            return await self._generate_error_response(current_slots)

    async def _extract_slot_data(
        self, user_message: str, current_slots: ProjectSlots
    ) -> Dict[str, Any]:
        """從用戶輸入中提取槽位數據"""
        try:
            # 使用LLM提取結構化數據
            prompt = self.prompts.get_extraction_prompt(user_message, current_slots)
            response = await self.llm_client.generate_response(prompt)

            # 解析JSON回應
            import json

            try:
                extracted_data = json.loads(response)
                return extracted_data
            except json.JSONDecodeError:
                logger.warning("LLM回應不是有效JSON，使用備用提取方法")
                return self._fallback_extraction(user_message)

        except Exception as e:
            logger.error(f"LLM提取失敗，使用備用方法: {e}")
            return self._fallback_extraction(user_message)

    def _fallback_extraction(self, user_message: str) -> Dict[str, Any]:
        """備用的數據提取方法"""
        extracted_data = {}

        # 簡單的關鍵詞匹配
        if "科技" in user_message or "電子" in user_message:
            extracted_data["industry"] = "科技業"

        if "充電線" in user_message:
            extracted_data["objective"] = "新產品研發"
            extracted_data["sub_industry"] = "充電線"

        if "消費" in user_message:
            extracted_data["objective"] = "消費品推廣"

        return extracted_data

    def _update_slots(
        self, current_slots: ProjectSlots, extracted_data: Dict[str, Any]
    ) -> ProjectSlots:
        """更新槽位數據"""
        updated_slots = current_slots.copy()

        for key, value in extracted_data.items():
            if hasattr(updated_slots, key) and value is not None:
                # 驗證值
                if self._validate_slot_value(key, value):
                    setattr(updated_slots, key, value)
                    logger.info(f"更新槽位 {key}: {value}")

        return updated_slots

    def _validate_slot_value(self, slot_key: str, value: Any) -> bool:
        """驗證槽位值"""
        try:
            # 將字符串鍵轉換為SlotKey枚舉
            slot_enum = SlotKey(slot_key)
            return validate_slot_value(slot_enum, value)
        except ValueError:
            logger.warning(f"未知的槽位鍵: {slot_key}")
            return False

    async def _generate_next_slot_response(
        self, next_slot: SlotKey, current_slots: ProjectSlots, user_message: str
    ) -> StateMachineOutput:
        """生成下一個槽位的回應"""
        try:
            # 生成洞察和問句
            prompt = self.prompts.get_next_slot_prompt(
                next_slot, current_slots, user_message
            )
            response = await self.llm_client.generate_response(prompt)

            # 解析回應
            parsed_response = self._parse_llm_response(response, next_slot)

            # 生成建議泡泡
            suggestions = self._generate_suggestions(next_slot, current_slots)

            # 計算完成度
            completion = calculate_completion(current_slots)
            missing_keys = get_missing_keys(current_slots)

            return StateMachineOutput(
                message=parsed_response.get("message", ""),
                next_question=parsed_response.get("next_question", ""),
                suggestions=suggestions,
                slot_writes=parsed_response.get("slot_writes"),
                rationale_cards=parsed_response.get("rationale_cards"),
                missing_keys=missing_keys,
                completion=completion,
            )

        except Exception as e:
            logger.error(f"生成下一個槽位回應失敗: {e}")
            return self._generate_fallback_response(next_slot, current_slots)

    def _parse_llm_response(self, response: str, next_slot: SlotKey) -> Dict[str, Any]:
        """解析LLM回應"""
        try:
            import json

            parsed = json.loads(response)

            # 確保回應符合合約
            result = {
                "message": parsed.get("message", ""),
                "next_question": parsed.get("next_question", ""),
                "slot_writes": parsed.get("slot_writes"),
            }

            # 如果是theme槽位，必須包含rationale_cards
            if next_slot == SlotKey.CAMPAIGN_THEME:
                result["rationale_cards"] = parsed.get("rationale_cards", [])

            return result

        except json.JSONDecodeError:
            logger.warning("LLM回應不是有效JSON，使用備用回應")
            return self._generate_fallback_llm_response(next_slot)

    def _generate_fallback_llm_response(self, next_slot: SlotKey) -> Dict[str, Any]:
        """生成備用的LLM回應"""
        fallback_responses = {
            SlotKey.INDUSTRY: {
                "message": "了解您的產業背景。請告訴我您的企劃目標是什麼？",
                "next_question": "您的企劃目標是什麼？",
            },
            SlotKey.OBJECTIVE: {
                "message": "清楚您的目標。接下來請描述目標受眾是誰？",
                "next_question": "目標受眾是誰？",
            },
            SlotKey.AUDIENCE_TARGETING: {
                "message": "受眾定位明確。請告訴我活動主題是什麼？",
                "next_question": "活動主題是什麼？",
            },
            SlotKey.CAMPAIGN_THEME: {
                "message": "主題很有創意。請告訴我活動期間？",
                "next_question": "活動期間是什麼時候？",
                "rationale_cards": [
                    {
                        "title": "為何選擇這個主題",
                        "bullets": [
                            "符合目標受眾喜好",
                            "與品牌調性一致",
                            "具有市場競爭力",
                        ],
                    }
                ],
            },
            SlotKey.CAMPAIGN_PERIOD: {
                "message": "時間安排合理。預算大概是多少？",
                "next_question": "預算大概是多少？",
            },
            SlotKey.TOTAL_BUDGET_TWD: {
                "message": "預算規劃清楚。會使用哪些媒體形式？",
                "next_question": "會使用哪些媒體形式？",
            },
            SlotKey.MEDIA_FORMATS: {
                "message": "媒體選擇合適。需要什麼類型的企劃？",
                "next_question": "需要什麼類型的企劃？",
            },
            SlotKey.PLAN_TYPE: {
                "message": "企劃類型明確。所有信息已收集完成！",
                "next_question": "專案需求收集完成！",
            },
        }

        return fallback_responses.get(
            next_slot,
            {"message": "請提供更多信息。", "next_question": "請繼續描述您的需求。"},
        )

    def _generate_suggestions(
        self, next_slot: SlotKey, current_slots: ProjectSlots
    ) -> List[SuggestionBubble]:
        """生成建議泡泡"""
        suggestions = []

        if next_slot == SlotKey.INDUSTRY:
            suggestions = [
                SuggestionBubble(
                    label="科技業",
                    slot=SlotKey.INDUSTRY,
                    value="科技業",
                    send_as_user="我是科技業",
                ),
                SuggestionBubble(
                    label="食品飲料",
                    slot=SlotKey.INDUSTRY,
                    value="食品飲料",
                    send_as_user="我是食品飲料業",
                ),
                SuggestionBubble(
                    label="服飾配件",
                    slot=SlotKey.INDUSTRY,
                    value="服飾配件",
                    send_as_user="我是服飾配件業",
                ),
                SuggestionBubble(
                    label="美妝保養",
                    slot=SlotKey.INDUSTRY,
                    value="美妝保養",
                    send_as_user="我是美妝保養業",
                ),
            ]

        elif next_slot == SlotKey.OBJECTIVE:
            suggestions = [
                SuggestionBubble(
                    label="新產品研發",
                    slot=SlotKey.OBJECTIVE,
                    value="新產品研發",
                    send_as_user="新產品研發",
                ),
                SuggestionBubble(
                    label="品牌推廣",
                    slot=SlotKey.OBJECTIVE,
                    value="品牌推廣",
                    send_as_user="品牌推廣",
                ),
                SuggestionBubble(
                    label="銷售提升",
                    slot=SlotKey.OBJECTIVE,
                    value="銷售提升",
                    send_as_user="銷售提升",
                ),
                SuggestionBubble(
                    label="市場擴展",
                    slot=SlotKey.OBJECTIVE,
                    value="市場擴展",
                    send_as_user="市場擴展",
                ),
            ]

        elif next_slot == SlotKey.MEDIA_FORMATS:
            suggestions = [
                SuggestionBubble(
                    label="社群媒體",
                    slot=SlotKey.MEDIA_FORMATS,
                    value="社群",
                    send_as_user="社群媒體",
                ),
                SuggestionBubble(
                    label="搜尋廣告",
                    slot=SlotKey.MEDIA_FORMATS,
                    value="搜尋",
                    send_as_user="搜尋廣告",
                ),
                SuggestionBubble(
                    label="影音廣告",
                    slot=SlotKey.MEDIA_FORMATS,
                    value="影音",
                    send_as_user="影音廣告",
                ),
                SuggestionBubble(
                    label="戶外廣告",
                    slot=SlotKey.MEDIA_FORMATS,
                    value="OOH",
                    send_as_user="戶外廣告",
                ),
                SuggestionBubble(
                    label="KOL合作",
                    slot=SlotKey.MEDIA_FORMATS,
                    value="KOL",
                    send_as_user="KOL合作",
                ),
            ]

        elif next_slot == SlotKey.PLAN_TYPE:
            for plan_type in PLAN_TYPE_OPTIONS:
                suggestions.append(
                    SuggestionBubble(
                        label=plan_type,
                        slot=SlotKey.PLAN_TYPE,
                        value=plan_type,
                        send_as_user=plan_type,
                    )
                )

        else:
            # 其他槽位使用通用建議
            suggestions = [
                SuggestionBubble(
                    label="請詳細描述",
                    slot=next_slot,
                    value="請詳細描述",
                    send_as_user="請詳細描述",
                )
            ]

        return suggestions[:5]  # 最多5個建議

    async def _generate_completion_response(
        self, completed_slots: ProjectSlots
    ) -> StateMachineOutput:
        """生成完成回應"""
        completion = calculate_completion(completed_slots)

        return StateMachineOutput(
            message="恭喜！所有必要信息已收集完成。我們將為您生成完整的企劃提案。",
            next_question="專案需求收集完成！",
            suggestions=[],
            missing_keys=[],
            completion=completion,
        )

    async def _generate_error_response(
        self, current_slots: ProjectSlots
    ) -> StateMachineOutput:
        """生成錯誤回應"""
        completion = calculate_completion(current_slots)
        missing_keys = get_missing_keys(current_slots)

        return StateMachineOutput(
            message="抱歉，處理您的輸入時遇到問題。請重新描述您的需求。",
            next_question="請重新描述您的需求",
            suggestions=[],
            missing_keys=missing_keys,
            completion=completion,
        )

    def _generate_fallback_response(
        self, next_slot: SlotKey, current_slots: ProjectSlots
    ) -> StateMachineOutput:
        """生成備用回應"""
        fallback_response = self._generate_fallback_llm_response(next_slot)
        suggestions = self._generate_suggestions(next_slot, current_slots)
        completion = calculate_completion(current_slots)
        missing_keys = get_missing_keys(current_slots)

        return StateMachineOutput(
            message=fallback_response.get("message", ""),
            next_question=fallback_response.get("next_question", ""),
            suggestions=suggestions,
            slot_writes=fallback_response.get("slot_writes"),
            rationale_cards=fallback_response.get("rationale_cards"),
            missing_keys=missing_keys,
            completion=completion,
        )
