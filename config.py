#!/usr/bin/env python3
"""
配置檔案
集中管理應用程式的所有設定參數
"""

import os

# Ollama 設定
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "localhost")
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", "11434"))
OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "gemma3:27b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))

# FastAPI 設定
FASTAPI_HOST = os.getenv("FASTAPI_HOST", "0.0.0.0")
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8000"))
FASTAPI_RELOAD = os.getenv("FASTAPI_RELOAD", "true").lower() == "true"

# 應用程式設定
COMPLETENESS_THRESHOLD = float(os.getenv("COMPLETENESS_THRESHOLD", "0.6"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = float(os.getenv("RETRY_DELAY", "1.0"))

# 日誌設定
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 企劃專案核心欄位
PROJECT_CORE_FIELDS = {
    "project_attributes": ["industry", "campaign", "is_urgent"],
    "time_budget": [
        "planning_due_date",
        "campaign_start_date",
        "campaign_end_date",
        "budget",
    ],
    "content_strategy": [
        "planning_types",
        "media_formats",
        "audience_lock",
        "audience_behavior",
        "client_materials",
        "client_requests",
    ],
    "technical_needs": ["technical_needs"],
}

# 企劃類型選項
PLANNING_TYPES = [
    "前端洞察分析",
    "策略提案",
    "產品包裝",
    "市場趨勢分析",
    "創意版位製作",
    "文案撰寫",
]

# 預定義選項池 - 用於AI快速選擇而不需要每次都重新生成
PREDEFINED_OPTIONS = {
    # 產業選項
    "industries": [
        "食品飲料",
        "服飾配件",
        "3C家電",
        "金融保險",
        "美妝保養",
        "運動健身",
        "汽車產業",
        "房地產",
        "旅遊觀光",
        "教育培訓",
        "醫療健康",
        "寵物用品",
        "母嬰用品",
        "家居用品",
        "數位娛樂",
        "遊戲產業",
        "電商平台",
        "其他產業",
    ],
    # 受眾情境選項
    "audience_scenarios": [
        "加到購物車未結帳",
        "觀看產品頁超過30秒",
        "搜尋品牌關鍵字",
        "瀏覽競品頁面",
        "點擊廣告連結",
        "分享產品內容",
        "加入會員",
        "下載APP",
        "填寫問卷",
        "預約試用",
        "關注社群帳號",
        "收藏商品",
    ],
    # 受眾族群選項
    "audience_demographics": [
        "女25至34 上班族",
        "男25至44 科技從業",
        "家庭主婦 育兒關注",
        "女18至24 學生族",
        "男35至50 主管階層",
        "銀髮族 退休人士",
        "新婚夫妻 購屋族",
        "單身貴族 小資族",
        "親子家庭 戶外活動",
        "商務人士 出差族",
        "健身愛好者 運動族",
        "美食愛好者 網紅族",
    ],
    # 受眾興趣選項
    "audience_interests": [
        "3C",
        "美妝保養",
        "運動健身",
        "美食烹飪",
        "旅遊攝影",
        "時尚穿搭",
        "投資理財",
        "親子育兒",
        "寵物照顧",
        "居家裝飾",
        "汽車改裝",
        "遊戲動漫",
        "音樂電影",
        "閱讀寫作",
        "手工藝品",
        "園藝種植",
        "戶外探險",
        "科技新知",
    ],
    # 受眾鎖定選項
    "audience_targeting": [
        "再行銷7天",
        "再行銷30天",
        "類似受眾1%",
        "類似受眾5%",
        "類似受眾10%",
        "興趣相似",
        "行為相似",
        "地理位置",
        "裝置類型",
        "時段鎖定",
        "排除既有客戶",
        "排除競品客戶",
        "排除無效用戶",
        "排除重複點擊",
    ],
    # 投放形式選項
    "media_formats": [
        "數位媒體",
        "社群媒體",
        "搜尋引擎廣告",
        "OTT/OTV",
        "聯播網",
        "Meta廣告",
        "YouTube廣告",
        "Google廣告",
        "Line廣告",
        "TikTok廣告",
        "電視廣告",
        "廣播廣告",
        "戶外廣告",
        "印刷媒體",
        "口碑論壇",
        "KOL合作",
        "網紅行銷",
        "內容行銷",
        "電子郵件",
        "簡訊行銷",
    ],
    # 預算範圍選項
    "budget_ranges": [
        "10萬以下",
        "10-30萬",
        "30-50萬",
        "50-100萬",
        "100-300萬",
        "300-500萬",
        "500-1000萬",
        "1000萬以上",
        "待確認",
    ],
    # 時程選項
    "timeline_options": [
        "1個月內",
        "1-3個月",
        "3-6個月",
        "6-12個月",
        "12個月以上",
        "待確認",
    ],
    # 緊急程度選項
    "urgency_levels": ["一般案件", "急件", "特急件", "待確認"],
}

# 智能選項生成規則 - 根據不同場景和缺失欄位選擇相關選項
OPTION_SELECTION_RULES = {
    "project_attributes.industry": {
        "options": "industries",
        "max_count": 6,
        "description": "請選擇產業類型",
    },
    "project_attributes.campaign": {
        "options": "industries",  # 可以根據產業推導活動主題
        "max_count": 4,
        "description": "請描述活動主題",
    },
    "content_strategy.audience_behavior.scenarios": {
        "options": "audience_scenarios",
        "max_count": 5,
        "description": "請選擇受眾情境",
    },
    "content_strategy.audience_behavior.demographic": {
        "options": "audience_demographics",
        "max_count": 4,
        "description": "請選擇受眾族群",
    },
    "content_strategy.audience_behavior.interests": {
        "options": "audience_interests",
        "max_count": 4,
        "description": "請選擇受眾興趣",
    },
    "content_strategy.audience_lock": {
        "options": "audience_targeting",
        "max_count": 4,
        "description": "請選擇受眾鎖定方式",
    },
    "content_strategy.media_formats": {
        "options": "media_formats",
        "max_count": 5,
        "description": "請選擇投放形式",
    },
    "time_budget.budget": {
        "options": "budget_ranges",
        "max_count": 4,
        "description": "請選擇預算範圍",
    },
    "time_budget.planning_due_date": {
        "options": "timeline_options",
        "max_count": 3,
        "description": "請選擇提案交付時程",
    },
    "project_attributes.is_urgent": {
        "options": "urgency_levels",
        "max_count": 3,
        "description": "請選擇緊急程度",
    },
}

# 快速回覆模板 - 根據不同完整性階段提供不同的快速回覆
QUICK_REPLY_TEMPLATES = {
    "initial": [  # 完整性 < 0.3
        "我想先了解基本資訊",
        "請幫我分析需求完整性",
        "我需要範例參考",
        "請提供產業資訊",
        "請說明活動主題",
    ],
    "progress": [  # 完整性 0.3-0.7
        "繼續補充細節",
        "我想看看目前的提案",
        "幫我檢查還缺什麼",
        "請提供受眾資訊",
        "請說明投放形式",
        "請提供預算範圍",
    ],
    "advanced": [  # 完整性 0.7-0.9
        "完成需求彙整",
        "產出最終提案",
        "儲存到專案池",
        "請確認最後細節",
        "請提供技術需求",
    ],
    "completion": [  # 完整性 > 0.9
        "完成需求彙整",
        "產出最終提案",
        "儲存到專案池",
        "開始執行企劃",
        "安排後續會議",
    ],
}

# 提案模板欄位
PROPOSAL_TEMPLATE_FIELDS = [
    "project_overview",
    "market_analysis",
    "competitive_analysis",
    "strategy_proposal",
    "media_plan",
    "budget_estimation",
    "timeline",
    "technical_requirements",
    "risk_assessment",
    "next_steps",
]

# 完整企劃專案示例數據
COMPLETE_PROJECT_EXAMPLES = {
    "淨水器品牌知名度提升": {
        "project_attributes": {
            "industry": "家電淨水",
            "campaign": "淨水器品牌知名度提升企劃",
            "is_urgent": True,
        },
        "time_budget": {
            "planning_due_date": "2024-10-15",
            "campaign_start_date": "2024-11-01",
            "campaign_end_date": "2025-03-31",
            "budget": 3000000,
        },
        "content_strategy": {
            "planning_types": ["前端洞察分析", "策略提案", "產品包裝", "創意版位製作"],
            "media_formats": [
                "OTT+OTV+聯播網(OMnet)",
                "Linelab(OMD)",
                "Meta+YT OMD自操",
            ],
            "audience_lock": "30-49歲家庭，重視健康、追求創新科技、關心環境永續",
            "audience_behavior": "具有前瞻思維、重視居家環境品質、有淨水器需求",
            "client_materials": "產品規格書、三家科技媒體合作資料",
            "client_requests": "提升品牌知名度(Awareness)、建立產品專業形象、擴大市場佔有率",
        },
        "technical_needs": "數位媒體投放系統、數據追蹤分析、科技媒體合作整合",
    },
    "眼鏡品牌市場分析": {
        "project_attributes": {
            "industry": "光學眼鏡",
            "campaign": "眼鏡品牌市場分析與廣宣企劃",
            "is_urgent": False,
        },
        "time_budget": {
            "planning_due_date": "2024-08-15",
            "campaign_start_date": "2024-09-01",
            "campaign_end_date": "2024-10-31",
            "budget": 2000000,
        },
        "content_strategy": {
            "planning_types": ["市場趨勢分析", "競品分析", "策略提案", "創意版位製作"],
            "media_formats": ["數位媒體", "社群媒體", "口碑論壇", "熱門文章"],
            "audience_lock": "25-45歲眼鏡使用者，重視品質、追求清晰視覺",
            "audience_behavior": "習慣線上搜尋產品資訊、重視品牌口碑、願意為品質付費",
            "client_materials": "前三年廣宣資料、競品分析報告、品牌聲量數據",
            "client_requests": "品牌聲量分析、口碑論壇分析、年度比較建議、競品策略參考",
        },
        "technical_needs": "品牌聲量監測系統、口碑分析工具、數據視覺化平台",
    },
    "科技公司新產品上市": {
        "project_attributes": {
            "industry": "科技產業",
            "campaign": "新產品上市行銷企劃",
            "is_urgent": True,
        },
        "time_budget": {
            "planning_due_date": "2023-12-15",
            "campaign_start_date": "2024-01-01",
            "campaign_end_date": "2024-03-31",
            "budget": 500000,
        },
        "content_strategy": {
            "planning_types": ["前端洞察分析", "策略提案", "創意版位製作", "文案撰寫"],
            "media_formats": ["數位媒體", "社群媒體", "搜尋引擎廣告"],
            "audience_lock": "25-35歲年輕上班族",
            "audience_behavior": (
                "數位原生世代，習慣線上購物，" "重視產品效能和性價比"
            ),
            "client_materials": "產品規格書、品牌指南、目標市場分析",
            "client_requests": ("建立品牌知名度，提升產品轉換率，" "擴大市場佔有率"),
        },
        "technical_needs": "響應式網頁設計、社群媒體整合、數據分析追蹤系統",
    },
}
