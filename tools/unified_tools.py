#!/usr/bin/env python3
"""
統一的工具執行器
整合所有功能工具，包括受眾洞察、選項生成等
"""

import json
import logging
import os
from typing import Any, Dict, List

from models.unified_models import (
    ProjectData,
    QuickReply,
    ToolResult,
    AudienceInsights,
    SixChapterReport,
)
from prompts.unified_prompts import UnifiedPrompts, build_six_chapter_prompt

logger = logging.getLogger(__name__)


class EvidenceProvider:
    """簡單的證據提供者"""

    def collect(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        return {"evidence": ctx.get("attachments", [])}


class SixChapterReportTool:
    """六章報告工具"""

    name = "six_chapter_report"

    def __init__(self, llm, evidence_provider: EvidenceProvider):
        self.llm = llm
        self.evidence = evidence_provider

    def execute(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        params = getattr(ctx, "params", None) or ctx.get("params", {})
        data = self.evidence.collect(ctx)
        prompt = build_six_chapter_prompt(params)
        resp = self.llm.generate_json(prompt, data)
        report = SixChapterReport.parse_obj(resp)
        strict = os.getenv("STRICT_CITATION") == "1"
        report = self._postfix(report, strict=strict)
        return {"report": report.dict(), "preview": {"completeness": 0.9}}

    def _postfix(self, report: SixChapterReport, strict: bool = False) -> SixChapterReport:
        # TODO: implement citation and style fixes when strict is True
        return report


class ToolExecutor:
    """統一的工具執行器"""

    def __init__(self, llm_client, evidence_provider: Any = None):
        """初始化工具執行器"""
        self.llm_client = llm_client
        self.evidence_provider = evidence_provider or EvidenceProvider()
        self.six_chapter_tool = SixChapterReportTool(
            llm_client, self.evidence_provider
        )

    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """執行指定的工具"""
        try:
            if tool_name == "generate_audience_insights":
                return await self.generate_audience_insights(**kwargs)
            elif tool_name == "generate_quick_replies":
                return await self.generate_quick_replies(**kwargs)
            elif tool_name == "evaluate_completeness":
                return await self.evaluate_completeness(**kwargs)
            elif tool_name == "generate_content_strategy":
                return await self.generate_content_strategy(**kwargs)
            elif tool_name == "extract_project_data":
                return await self.extract_project_data(**kwargs)
            elif tool_name == "six_chapter_report":
                ctx = kwargs.get("ctx", {})
                data = self.six_chapter_tool.execute(ctx)
                return ToolResult(
                    success=True,
                    data=data,
                    message="六章報告生成成功",
                    metadata={"tool": self.six_chapter_tool.name},
                )
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"未知的工具: {tool_name}",
                    metadata={"tool_name": tool_name},
                )
        except Exception as e:
            logger.error(f"執行工具 {tool_name} 時發生錯誤: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"工具執行失敗: {str(e)}",
                metadata={"tool_name": tool_name, "error": str(e)},
            )

    async def generate_audience_insights(self, project_data: ProjectData) -> ToolResult:
        """生成受眾洞察"""
        try:
            # 構建受眾分析提示詞
            prompt = UnifiedPrompts.get_system_prompt("audience")

            # 添加專案上下文
            context = f"""
專案資訊：
- 產業: {project_data.project_attributes.industry or '未指定'}
- 活動主題: {project_data.project_attributes.campaign or '未指定'}
- 預算: {project_data.time_budget.budget or '未指定'}
- 媒體形式: {project_data.content_strategy.media_formats or '未指定'}

請基於以上資訊分析目標受眾特徵。
"""

            full_prompt = prompt + context

            # 調用LLM生成洞察
            response = await self.llm_client.generate_response(full_prompt)

            # 解析回應並構建受眾洞察對象
            insights = self._parse_audience_insights(response)

            return ToolResult(
                success=True,
                data=insights,
                message="受眾洞察生成成功",
                metadata={"tool": "generate_audience_insights"},
            )

        except Exception as e:
            logger.error(f"生成受眾洞察失敗: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"生成受眾洞察失敗: {str(e)}",
                metadata={"tool": "generate_audience_insights", "error": str(e)},
            )

    async def generate_quick_replies(
        self, user_message: str, project_data: ProjectData, context: str = "general"
    ) -> ToolResult:
        """生成快速回覆選項"""
        try:
            # 構建快速回覆生成提示詞（依缺失欄位與上下文動態產生）
            prompt = UnifiedPrompts.get_system_prompt("quick_reply")

            # 找出缺口
            missing = []
            if not project_data.project_attributes.industry:
                missing.append("industry")
            if not project_data.project_attributes.campaign:
                missing.append("campaign_theme")
            if not project_data.time_budget.planning_due_date:
                missing.append("proposal_due_date")
            if (
                not project_data.time_budget.campaign_start_date
                or not project_data.time_budget.campaign_end_date
            ):
                missing.append("campaign_period")
            if not project_data.time_budget.budget:
                missing.append("total_budget")
            if not project_data.content_strategy.media_formats:
                missing.append("media_formats")
            if not project_data.content_strategy.planning_types:
                missing.append("plan_type")
            if not project_data.content_strategy.audience_lock:
                missing.append("audience_targeting")
            if not project_data.content_strategy.audience_behavior:
                missing.append("audience_behavior")

            # 添加對話上下文
            context_info = f"""
用戶訊息: {user_message}

專案狀態: {self._get_project_summary(project_data)}
缺失欄位: {', '.join(missing) or '無'}

請根據缺失欄位動態生成3-5個快速回覆，每個選項要能直接填入關鍵欄位或推進下一步，
例如提供『受眾鎖定』、『媒體形式』、『預算範圍』、『活動期間』等具體可選文字。
輸出 JSON 陣列，每個元素含 text、value 欄位。
"""

            full_prompt = prompt + context_info

            # 調用LLM生成選項
            response = await self.llm_client.generate_response(full_prompt)

            # 解析回應並構建快速回覆選項；若 LLM 無法給出 JSON，就用缺失欄位生成預設泡泡
            quick_replies = self._parse_quick_replies(response)
            if not quick_replies:
                fallback = []
                if "audience_targeting" in missing:
                    for lbl in ["家庭親子", "年輕族群", "企業決策者", "教育單位"]:
                        fallback.append(
                            QuickReply(text=lbl, value=lbl, priority=len(fallback) + 1)
                        )
                if "media_formats" in missing:
                    for lbl in ["社群", "搜尋", "影音", "OOH"]:
                        fallback.append(
                            QuickReply(text=lbl, value=lbl, priority=len(fallback) + 1)
                        )
                if "total_budget" in missing:
                    for lbl in ["50萬", "100萬", "300萬", "500萬"]:
                        fallback.append(
                            QuickReply(text=lbl, value=lbl, priority=len(fallback) + 1)
                        )
                if not fallback:
                    fallback = [
                        QuickReply(
                            text="提供更多資訊", value="提供更多資訊", priority=1
                        ),
                        QuickReply(text="下一步建議", value="下一步建議", priority=2),
                    ]
                return ToolResult(
                    success=True,
                    data=fallback,
                    message="快速回覆選項生成成功",
                    metadata={"tool": "generate_quick_replies", "fallback": True},
                )

            return ToolResult(
                success=True,
                data=quick_replies,
                message="快速回覆選項生成成功",
                metadata={"tool": "generate_quick_replies"},
            )

        except Exception as e:
            logger.error(f"生成快速回覆選項失敗: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"生成快速回覆選項失敗: {str(e)}",
                metadata={"tool": "generate_quick_replies", "error": str(e)},
            )

    async def evaluate_completeness(self, project_data: ProjectData) -> ToolResult:
        """評估專案完整度"""
        try:
            # 構建完整度評估提示詞
            prompt = UnifiedPrompts.get_system_prompt("completeness")

            # 添加專案數據
            context = f"""
專案數據:
{self._format_project_for_evaluation(project_data)}

請評估專案的完整度並提供分數和建議。
"""

            full_prompt = prompt + context

            # 調用LLM評估完整度
            response = await self.llm_client.generate_response(full_prompt)

            # 解析回應
            evaluation = self._parse_completeness_evaluation(response)

            return ToolResult(
                success=True,
                data=evaluation,
                message="專案完整度評估完成",
                metadata={"tool": "evaluate_completeness"},
            )

        except Exception as e:
            logger.error(f"評估專案完整度失敗: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"評估專案完整度失敗: {str(e)}",
                metadata={"tool": "evaluate_completeness", "error": str(e)},
            )

    async def generate_content_strategy(self, project_data: ProjectData) -> ToolResult:
        """生成內容策略建議"""
        try:
            # 構建內容策略生成提示詞
            prompt = UnifiedPrompts.get_system_prompt("strategy")

            # 添加專案和受眾資訊
            context = f"""
專案資訊:
{self._format_project_for_strategy(project_data)}

請基於以上資訊生成內容策略建議。
"""

            full_prompt = prompt + context

            # 調用LLM生成策略
            response = await self.llm_client.generate_response(full_prompt)

            # 解析回應
            strategy = self._parse_content_strategy(response)

            return ToolResult(
                success=True,
                data=strategy,
                message="內容策略生成成功",
                metadata={"tool": "generate_content_strategy"},
            )

        except Exception as e:
            logger.error(f"生成內容策略失敗: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"生成內容策略失敗: {str(e)}",
                metadata={"tool": "generate_content_strategy", "error": str(e)},
            )

    async def extract_project_data(self, user_message: str) -> ToolResult:
        """從用戶訊息中提取專案數據"""
        try:
            # 構建數據提取提示詞
            prompt = UnifiedPrompts.get_system_prompt("extraction")

            # 添加用戶訊息
            full_prompt = f"{prompt}\n\n用戶訊息: {user_message}"

            # 調用LLM提取數據
            response = await self.llm_client.generate_response(full_prompt)

            # 解析回應
            extracted_data = self._parse_extracted_data(response)

            return ToolResult(
                success=True,
                data=extracted_data,
                message="專案數據提取成功",
                metadata={"tool": "extract_project_data"},
            )

        except Exception as e:
            logger.error(f"提取專案數據失敗: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"提取專案數據失敗: {str(e)}",
                metadata={"tool": "extract_project_data", "error": str(e)},
            )

    def _parse_audience_insights(self, response: str) -> AudienceInsights:
        """解析受眾洞察回應"""
        try:
            # 嘗試解析JSON回應
            if "{" in response and "}" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
                data = json.loads(json_str)

                return AudienceInsights(**data)
            else:
                # 如果無法解析JSON，創建基本洞察對象
                return AudienceInsights(
                    target_demographics={"note": "需要進一步分析"},
                    psychographic_profile={"note": "需要進一步分析"},
                    behavior_patterns=["需要進一步分析"],
                    pain_points=["需要進一步分析"],
                    motivations=["需要進一步分析"],
                    media_preferences=["需要進一步分析"],
                )
        except Exception as e:
            logger.warning(f"解析受眾洞察失敗，使用預設值: {e}")
            return AudienceInsights()

    def _parse_quick_replies(self, response: str) -> List[QuickReply]:
        """解析快速回覆選項"""
        try:
            # 嘗試解析JSON回應
            if "[" in response and "]" in response:
                start = response.find("[")
                end = response.rfind("]") + 1
                json_str = response[start:end]
                data = json.loads(json_str)

                quick_replies = []
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        quick_replies.append(
                            QuickReply(
                                text=item.get("text", f"選項{i+1}"),
                                value=item.get("value", item.get("text", f"選項{i+1}")),
                                priority=i + 1,
                            )
                        )
                    else:
                        quick_replies.append(
                            QuickReply(text=str(item), value=str(item), priority=i + 1)
                        )

                return quick_replies
            else:
                # 如果無法解析JSON，生成基本選項
                return [
                    QuickReply(text="繼續", value="continue", priority=1),
                    QuickReply(text="需要更多資訊", value="more_info", priority=2),
                    QuickReply(text="完成", value="complete", priority=3),
                ]
        except Exception as e:
            logger.warning(f"解析快速回覆選項失敗，使用預設值: {e}")
            return [
                QuickReply(text="繼續", value="continue", priority=1),
                QuickReply(text="需要更多資訊", value="more_info", priority=2),
                QuickReply(text="完成", value="complete", priority=3),
            ]

    def _parse_completeness_evaluation(self, response: str) -> Dict[str, Any]:
        """解析完整度評估"""
        try:
            # 嘗試解析JSON回應
            if "{" in response and "}" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
                return json.loads(json_str)
            else:
                # 如果無法解析JSON，返回基本評估
                return {
                    "completeness_score": 50.0,
                    "missing_fields": ["需要進一步分析"],
                    "next_action": "繼續收集資訊",
                    "is_ready": False,
                }
        except Exception as e:
            logger.warning(f"解析完整度評估失敗，使用預設值: {e}")
            return {
                "completeness_score": 50.0,
                "missing_fields": ["需要進一步分析"],
                "next_action": "繼續收集資訊",
                "is_ready": False,
            }

    def _parse_content_strategy(self, response: str) -> Dict[str, Any]:
        """解析內容策略"""
        try:
            # 嘗試解析JSON回應
            if "{" in response and "}" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
                return json.loads(json_str)
            else:
                # 如果無法解析JSON，返回基本策略
                return {
                    "planning_types": ["需要進一步分析"],
                    "media_formats": ["需要進一步分析"],
                    "content_themes": ["需要進一步分析"],
                    "timing_suggestions": ["需要進一步分析"],
                    "evaluation_metrics": ["需要進一步分析"],
                }
        except Exception as e:
            logger.warning(f"解析內容策略失敗，使用預設值: {e}")
            return {
                "planning_types": ["需要進一步分析"],
                "media_formats": ["需要進一步分析"],
                "content_themes": ["需要進一步分析"],
                "timing_suggestions": ["需要進一步分析"],
                "evaluation_metrics": ["需要進一步分析"],
            }

    def _parse_extracted_data(self, response: str) -> Dict[str, Any]:
        """解析提取的專案數據"""
        try:
            # 嘗試解析JSON回應
            if "{" in response and "}" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
                return json.loads(json_str)
            else:
                # 如果無法解析JSON，返回空數據
                return {}
        except Exception as e:
            logger.warning(f"解析提取數據失敗: {e}")
            return {}

    def _get_project_summary(self, project_data: ProjectData) -> str:
        """獲取專案摘要"""
        summary = []

        if project_data.project_attributes.industry:
            summary.append(f"產業: {project_data.project_attributes.industry}")
        if project_data.project_attributes.campaign:
            summary.append(f"主題: {project_data.project_attributes.campaign}")
        if project_data.time_budget.budget:
            summary.append(f"預算: {project_data.time_budget.budget}")

        return " | ".join(summary) if summary else "專案尚未開始"

    def _format_project_for_evaluation(self, project_data: ProjectData) -> str:
        """格式化專案數據用於評估"""
        return self._get_project_summary(project_data)

    def _format_project_for_strategy(self, project_data: ProjectData) -> str:
        """格式化專案數據用於策略生成"""
        return self._get_project_summary(project_data)
