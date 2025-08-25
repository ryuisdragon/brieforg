#!/usr/bin/env python3
"""
統一的會話單例入口
所有模組請從這裡取得唯一的會話管理器實例
"""

from services.unified_session_manager import UnifiedSessionManager

# 唯一來源（檔案型持久化管理器）
manager = UnifiedSessionManager()



