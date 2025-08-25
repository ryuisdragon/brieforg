@echo off
chcp 65001 >nul
title 企劃需求助手 - 系統啟動器

echo.
echo ============================================================
echo 🎯 企劃需求助手 - 系統啟動器
echo ============================================================
echo.

echo 🔍 檢查 Python 環境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 錯誤: 找不到 Python，請先安裝 Python 3.7+
    pause
    exit /b 1
)

echo ✅ Python 環境正常
echo.

echo 🔍 檢查 Ollama 服務...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  警告: 找不到 Ollama，請先安裝 Ollama
    echo 下載地址: https://ollama.ai/
    echo.
    echo 是否繼續啟動前端？(y/n)
    set /p choice=
    if /i "%choice%" neq "y" (
        echo 系統啟動已取消
        pause
        exit /b 1
    )
) else (
    echo ✅ Ollama 已安裝
    echo.
    echo 🚀 啟動 Ollama 服務...
    start "Ollama Service" ollama serve
    timeout /t 3 /nobreak >nul
)

echo.
echo 🚀 啟動 FastAPI 後端服務...
start "Backend Service" python start_refactored_unified.py

echo.
echo ⏳ 等待後端服務啟動...
timeout /t 5 /nobreak >nul

echo.
echo 🚀 啟動前端演示服務器...
start "Frontend Server" python start_frontend_demo.py

echo.
echo ============================================================
echo ✅ 系統啟動完成！
echo ============================================================
echo.
echo 📍 後端 API: http://localhost:8000
echo 🌐 前端界面: http://localhost:8080/frontend_glass.html
echo 📚 API 文檔: http://localhost:8000/docs
echo.
echo 💡 使用提示:
echo 1. 後端服務會在 http://localhost:8000 運行
echo 2. 前端界面會在 http://localhost:8080 運行
echo 3. 使用前端的"測試連線"按鈕檢查後端狀態
echo 4. 選擇對話模式或表單模式開始使用
echo.
echo 🔧 停止服務: 關閉對應的命令行窗口
echo.

pause

