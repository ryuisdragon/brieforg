#!/usr/bin/env python3
"""
DEPRECATED: 此檔案僅作為過渡期入口。
請改用新入口：`app_refactored_unified:app`。
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from config import FASTAPI_HOST, FASTAPI_PORT

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 建立 FastAPI 應用
app = FastAPI(
    title="統一企劃需求助手 API",
    description="模組化架構的企劃專案管理和受眾分析服務",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 設定 CORS（上線前請以 CORS_ORIGINS 白名單收斂）
import os

_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(router, prefix="/api/v2")


# 根路徑
@app.get("/")
async def root():
    """根路徑"""
    return {
        "message": "統一企劃需求助手服務",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v2/health",
    }


# 向後兼容的路徑重定向
@app.get("/health")
async def legacy_health():
    """向後兼容的健康檢查"""
    return {"status": "healthy", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app_unified:app",
        host=FASTAPI_HOST,
        port=FASTAPI_PORT,
        reload=True,
        log_level="info",
    )
