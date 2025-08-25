#!/usr/bin/env python3
"""
統一的提示詞管理
整合所有系統提示詞和對話模板
"""

from typing import Dict, Any


class UnifiedPrompts:
    """統一的提示詞管理類"""

    # 系統角色定義
    SYSTEM_ROLE = """你是一個專業的企劃需求助手，專門幫助客戶收集和分析企劃專案需求。
你的主要職責包括：
1. 收集專案基本資訊（產業、活動主題、時間、預算等）
2. 分析受眾特徵和行為模式
3. 提供內容策略建議
4. 識別技術需求和限制
5. 生成快速回覆選項幫助用戶選擇

請保持專業、友善且高效的對話風格。"""

    # 專案數據提取提示詞
    PROJECT_EXTRACTION_PROMPT = """請從用戶的訊息中提取專案相關資訊，並以JSON格式回傳。

需要提取的欄位：
- project_attributes.industry: 產業類型
- project_attributes.campaign: 活動主題
- project_attributes.is_urgent: 是否急案
- time_budget.planning_due_date: 提案交付日期
- time_budget.campaign_start_date: 活動開始日期
- time_budget.campaign_end_date: 活動結束日期
- time_budget.budget: 預算金額
- content_strategy.planning_types: 企劃類型
- content_strategy.media_formats: 媒體/投放形式
- content_strategy.audience_lock: 受眾鎖定
- content_strategy.audience_behavior: 受眾行為
- content_strategy.client_materials: 客戶素材
- content_strategy.client_requests: 客戶要求
- technical_needs.technical_needs: 技術需求

如果某個欄位無法從訊息中確定，請設為null。
只回傳JSON格式，不要包含其他文字。"""

    # 受眾分析提示詞
    AUDIENCE_ANALYSIS_PROMPT = """基於專案資訊，請分析目標受眾特徵並生成洞察。

分析維度：
1. 人口統計特徵（年齡、性別、收入、教育程度等）
2. 心理特徵（價值觀、生活方式、興趣愛好等）
3. 行為模式（消費習慣、媒體使用、社交行為等）
4. 痛點和動機
5. 媒體偏好

請以結構化方式回傳分析結果，並提供具體的受眾洞察建議。"""

    # 內容策略生成提示詞
    CONTENT_STRATEGY_PROMPT = """基於專案需求和受眾分析，請生成內容策略建議。

策略要素：
1. 企劃類型建議（活動策劃、品牌推廣、產品發布等）
2. 媒體形式選擇（社交媒體、電視廣告、戶外廣告等）
3. 內容主題方向
4. 傳播時機建議
5. 效果評估指標

請提供具體可執行的策略建議。"""

    # 快速回覆選項生成提示詞
    QUICK_REPLY_GENERATION_PROMPT = """基於當前對話上下文和專案狀態，請生成3-5個快速回覆選項。

選項要求：
1. 符合用戶當前需求
2. 幫助推進專案進度
3. 提供具體可選擇的內容
4. 按優先級排序

格式：每個選項包含text（顯示文字）和value（實際值）。"""

    # 專案完整度評估提示詞
    COMPLETENESS_EVALUATION_PROMPT = """請評估當前專案數據的完整度，並指出缺失的關鍵資訊。

評估標準：
- 完整度分數（0-100）
- 缺失的必填欄位
- 建議的下一步行動
- 專案是否可進入下一階段

請提供結構化的評估結果。"""

    # 對話流程控制提示詞
    CONVERSATION_FLOW_PROMPT = """基於當前專案狀態和用戶輸入，請決定下一步對話策略。

策略選項：
1. 收集更多資訊（提問）
2. 提供選項供選擇
3. 生成受眾洞察
4. 提供內容策略建議
5. 確認專案完整性
6. 總結並結束對話

請選擇最適合的策略並說明理由。"""

    # 錯誤處理提示詞
    ERROR_HANDLING_PROMPT = """當遇到錯誤或無法理解用戶輸入時，請：

1. 禮貌地說明問題
2. 提供可能的解決方案
3. 建議用戶重新表述
4. 保持對話的連續性

請以友善且專業的態度處理錯誤情況。"""

    @classmethod
    def get_system_prompt(cls, context: str = "general") -> str:
        """根據上下文獲取系統提示詞"""
        prompts = {
            "general": cls.SYSTEM_ROLE,
            "extraction": cls.PROJECT_EXTRACTION_PROMPT,
            "audience": cls.AUDIENCE_ANALYSIS_PROMPT,
            "strategy": cls.CONTENT_STRATEGY_PROMPT,
            "quick_reply": cls.QUICK_REPLY_GENERATION_PROMPT,
            "completeness": cls.COMPLETENESS_EVALUATION_PROMPT,
            "flow": cls.CONVERSATION_FLOW_PROMPT,
            "error": cls.ERROR_HANDLING_PROMPT,
        }
        return prompts.get(context, cls.SYSTEM_ROLE)

    @classmethod
    def get_conversation_prompt(
        cls, user_message: str, project_data: Dict[str, Any], context: str = "general"
    ) -> str:
        """生成完整的對話提示詞"""
        system_prompt = cls.get_system_prompt(context)

        prompt = f"""
{system_prompt}

當前專案狀態：
{cls._format_project_data(project_data)}

用戶訊息：{user_message}

請根據以上資訊提供回應。
"""
        return prompt.strip()

    @classmethod
    def _format_project_data(cls, project_data: Dict[str, Any]) -> str:
        """格式化專案數據用於提示詞"""
        if not project_data:
            return "專案尚未開始"

        formatted = []
        for section, data in project_data.items():
            if data and isinstance(data, dict):
                formatted.append(f"{section}:")
                for key, value in data.items():
                    if value:
                        formatted.append(f"  - {key}: {value}")

        return "\n".join(formatted) if formatted else "專案數據不完整"


def build_six_chapter_prompt(vars: dict) -> dict:
    sys = (
        "你是媒體廣告資深企劃與策略敘事者，\n"
        "嚴禁臆測，六章輸出，每句關鍵主張句尾需含〔來源｜YYYY-MM 或 YYYY-MM-DD〕，\n"
        "章節必為段落非條列，句長控制，含因果橋接與可比較數字，台灣優先並標註可比性。"
    )
    tool = (
        "請輸出 JSON，字段為\n"
        "sections=[{id,title,body}], 其中 body 為可直接貼進 PPT 的中文段落，\n"
        "段內括號提供圖表或設計建議，引用需在同句句尾。"
    )
    user = (
        f"品類={vars.get('category')}，品牌聚焦={vars.get('brand_focus')}，\n"
        f"觀測窗={vars.get('window')}，語系=zh-TW，\n"
        "可用證據會由 EvidenceProvider 插入到 context.evidence。"
    )
    return {"system": sys, "tool": tool, "user": user}
