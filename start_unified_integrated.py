#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
啟動整合後的統一企劃需求助手服務
整合了所有功能：企劃專案管理、受眾教練、對話式需求收集
自動啟動 Ollama 服務並載入 gemma3:27b 模型
"""

import subprocess
import time
import requests
import sys
import os
from pathlib import Path


def check_ollama_service():
    """檢查 Ollama 服務是否運行"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"✅ Ollama 服務正常運行")
            print(f"📋 可用模型: {[model['name'] for model in models]}")
            return True
        else:
            print(f"❌ Ollama 服務回應異常: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 無法連接到 Ollama 服務: {e}")
        return False


def start_ollama_service():
    """啟動 Ollama 服務"""
    print("🚀 啟動 Ollama 服務...")

    try:
        # 檢查 Ollama 是否已安裝
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Ollama 未安裝，請先安裝 Ollama")
            print("💡 安裝指南: https://ollama.ai/download")
            return False

        print("✅ Ollama 已安裝")

        # 啟動 Ollama 服務
        print("🔄 啟動 Ollama 服務...")
        subprocess.Popen(
            ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

        # 等待服務啟動
        print("⏳ 等待 Ollama 服務啟動...")
        for i in range(30):  # 最多等待30秒
            if check_ollama_service():
                print("✅ Ollama 服務啟動成功")
                return True
            time.sleep(1)
            if i % 5 == 0:
                print(f"⏳ 等待中... ({i+1}/30)")

        print("❌ Ollama 服務啟動超時")
        return False

    except Exception as e:
        print(f"❌ 啟動 Ollama 服務失敗: {e}")
        return False


def ensure_gemma_model():
    """確保 gemma3:27b 模型可用"""
    try:
        print("🔍 檢查 gemma3:27b 模型...")
        response = requests.get("http://localhost:11434/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [model["name"] for model in models]

            if "gemma3:27b" in model_names:
                print("✅ gemma3:27b 模型已可用")
                return True
            else:
                print("📥 下載 gemma3:27b 模型...")
                print("💡 這可能需要幾分鐘時間，請耐心等待...")

                # 下載模型
                subprocess.run(
                    ["ollama", "pull", "gemma3:27b"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                print("✅ gemma3:27b 模型下載完成")
                return True
        else:
            print(f"❌ 無法獲取模型列表: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ 檢查/下載模型失敗: {e}")
        return False


def check_dependencies():
    """檢查依賴是否已安裝"""
    try:
        import fastapi
        import uvicorn
        import pydantic
        import requests

        print("✅ 所有依賴已安裝")
        return True
    except ImportError as e:
        print(f"❌ 缺少依賴: {e}")
        print("請執行: pip install -r requirements.txt")
        return False


def main():
    """主函數"""
    print("🚀 啟動整合後的統一企劃需求助手服務")
    print("📝 版本: 2.0.0 (整合版)")
    print("=" * 60)

    # 檢查依賴
    if not check_dependencies():
        return 1

    # 檢查 Ollama 服務
    if not check_ollama_service():
        print("\n🔄 嘗試啟動 Ollama 服務...")
        if not start_ollama_service():
            print("❌ 無法啟動 Ollama 服務")
            print("💡 請手動啟動: ollama serve")
            return 1

    # 確保 gemma3:27b 模型可用
    if not ensure_gemma_model():
        print("❌ 無法確保 gemma3:27b 模型可用")
        return 1

    print("\n🌐 啟動 FastAPI 服務器...")
    print(f"📡 API 端點: http://localhost:8000")
    print(f"📖 API 文檔: http://localhost:8000/docs")
    print(f"🔍 健康檢查: http://localhost:8000/health")
    print("\n💡 整合功能:")
    print("  - 企劃專案管理 (原有功能)")
    print("  - 受眾教練系統 (增強版)")
    print("  - 對話式需求收集 (/chat/message)")
    print("  - AI 自動補全 (/chat/autofill)")
    print("  - 會話管理 (/chat/sessions)")
    print("  - 受眾洞察分析 (/audience-coach/insights)")
    print("  - 受眾策略建議 (/audience-coach/strategy)")
    print("\n按 Ctrl+C 停止服務")
    print("-" * 60)

    try:
        # 啟動 FastAPI 服務器
        import uvicorn

        uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
    except KeyboardInterrupt:
        print("\n👋 服務器已停止")
        return 0
    except Exception as e:
        print(f"❌ 啟動服務器失敗: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
