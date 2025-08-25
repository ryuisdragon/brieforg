"""
DEPRECATED SHIM: 請改用 `from services.agent import agent`
此模組僅提供 `unified_agent` 的相容 re-export
"""

from services.agent import agent as unified_agent  # noqa: F401
