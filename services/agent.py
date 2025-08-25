#!/usr/bin/env python3
"""
統一代理單例入口
所有模組請從這裡取得唯一代理與工具執行器（新版、異步）
"""

from services.llm_client import LLMClient
from tools.unified_tools import ToolExecutor
from agents.unified_planning_agent import UnifiedPlanningAgent

# LLM 客戶端
_llm = LLMClient()

# 工具執行器
tool_executor = ToolExecutor(_llm)

# 統一代理（新版）
agent = UnifiedPlanningAgent(_llm, tool_executor)

