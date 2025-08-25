#!/usr/bin/env python3
"""
狀態機硬控流程提示詞
實現固定的槽位收集流程提示詞
"""

# from typing import Dict, Any  # 暂时未使用
from models.state_machine_models import SlotKey, ProjectSlots


class StateMachinePrompts:
    """狀態機提示詞管理器"""

    def get_extraction_prompt(
        self, user_message: str, current_slots: ProjectSlots
    ) -> str:
        """獲取數據提取提示詞"""
        filled_slots = []
        for slot_key in SlotKey:
            if hasattr(current_slots, slot_key.value):
                value = getattr(current_slots, slot_key.value)
                if value is not None:
                    filled_slots.append(f"{slot_key.value}: {value}")

        filled_info = "\n".join(filled_slots) if filled_slots else "無"

        return f"""你是一個專業的企劃需求分析助手。請從用戶的輸入中提取相關的槽位信息。

當前已填充的槽位：
{filled_info}

用戶輸入：{user_message}

請分析用戶輸入，提取以下槽位信息（如果有的話）：
- industry: 產業類型
- objective: 企劃目標
- audience_targeting: 目標受眾
- campaign_theme: 活動主題
- campaign_period: 活動期間 {{start: "開始日期", end: "結束日期"}}
- total_budget_twd: 預算金額（整數）
- media_formats: 媒體形式列表（限於：社群、搜尋、影音、OOH、KOL）
- plan_type: 企劃類型
- sub_industry: 子產業/產品線（可選）

請只返回JSON格式，不要其他內容：

{{
  "industry": "提取的產業或null",
  "objective": "提取的目標或null",
  "audience_targeting": "提取的受眾或null",
  "campaign_theme": "提取的主題或null",
  "campaign_period": {{"start": "開始日期", "end": "結束日期"}} 或 null,
  "total_budget_twd": 預算數字或null,
  "media_formats": ["媒體1", "媒體2"] 或 null,
  "plan_type": "企劃類型或null",
  "sub_industry": "子產業或null"
}}"""

    def get_next_slot_prompt(
        self, next_slot: SlotKey, current_slots: ProjectSlots, user_message: str
    ) -> str:
        """獲取下一個槽位的提示詞"""

        slot_descriptions = {
            SlotKey.INDUSTRY: "產業類型",
            SlotKey.OBJECTIVE: "企劃目標",
            SlotKey.AUDIENCE_TARGETING: "目標受眾",
            SlotKey.CAMPAIGN_THEME: "活動主題",
            SlotKey.CAMPAIGN_PERIOD: "活動期間",
            SlotKey.TOTAL_BUDGET_TWD: "預算金額",
            SlotKey.MEDIA_FORMATS: "媒體形式",
            SlotKey.PLAN_TYPE: "企劃類型",
        }

        slot_desc = slot_descriptions.get(next_slot, "相關信息")

        filled_slots = []
        for slot_key in SlotKey:
            if hasattr(current_slots, slot_key.value):
                value = getattr(current_slots, slot_key.value)
                if value is not None:
                    filled_slots.append(f"{slot_key.value}: {value}")

        filled_info = "\n".join(filled_slots) if filled_slots else "無"

        return f"""你是一個專業的企劃需求分析助手。請根據當前信息生成回應和下一個問題。

當前已收集的信息：
{filled_info}

用戶最新輸入：{user_message}

下一個需要收集的槽位：{slot_desc}

請按照以下格式回應：

1. message: 兩句話，第一句點出1-3個關鍵信息（名詞短語），第二句用問句帶出下一步。總字數≤100字。
2. next_question: 針對{slot_desc}的具體問句。

重要規則：
- 禁用"已成功提取專案資訊"等客套話
- 回應必須簡潔有力，直接切入重點
- 問句要具體明確，容易回答

如果是 campaign_theme 槽位，還需要包含：
- rationale_cards: 理由卡片，說明為何選擇這個主題

請只返回JSON格式：

{{
  "message": "兩句洞察＋問句，≤100字",
  "next_question": "針對{slot_desc}的問句"
}}"""

    def get_completion_prompt(self, completed_slots: ProjectSlots) -> str:
        """獲取完成提示詞"""
        filled_slots = []
        for slot_key in SlotKey:
            if hasattr(completed_slots, slot_key.value):
                value = getattr(completed_slots, slot_key.value)
                if value is not None:
                    filled_slots.append(f"{slot_key.value}: {value}")

        slots_summary = "\n".join(filled_slots)

        return f"""恭喜！所有必要信息已收集完成。請生成完成回應。

已收集的完整信息：
{slots_summary}

請生成：
1. 完成確認信息
2. 下一步建議

回應要求：
- 簡潔有力，確認信息收集完成
- 提供明確的下一步行動建議
- 避免冗長的總結

請只返回JSON格式：

{{
  "message": "完成確認信息",
  "next_question": "下一步建議"
}}"""
