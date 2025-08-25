# 企劃需求助手 - 系統啟動器 (PowerShell)
# 設置控制台編碼
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "🎯 企劃需求助手 - 系統啟動器"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🎯 企劃需求助手 - 系統啟動器" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 檢查 Python 環境
Write-Host "🔍 檢查 Python 環境..." -ForegroundColor Green
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Python 環境正常: $pythonVersion" -ForegroundColor Green
    }
    else {
        throw "Python 執行失敗"
    }
}
catch {
    Write-Host "❌ 錯誤: 找不到 Python，請先安裝 Python 3.7+" -ForegroundColor Red
    Read-Host "按 Enter 鍵退出"
    exit 1
}

Write-Host ""

# 檢查 Ollama 服務
Write-Host "🔍 檢查 Ollama 服務..." -ForegroundColor Green
try {
    $ollamaVersion = ollama --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Ollama 已安裝: $ollamaVersion" -ForegroundColor Green
        Write-Host ""
        Write-Host "🚀 啟動 Ollama 服務..." -ForegroundColor Yellow
        
        # 啟動 Ollama 服務
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
        Start-Sleep -Seconds 3
    }
    else {
        throw "Ollama 執行失敗"
    }
}
catch {
    Write-Host "⚠️  警告: 找不到 Ollama，請先安裝 Ollama" -ForegroundColor Yellow
    Write-Host "下載地址: https://ollama.ai/" -ForegroundColor Cyan
    Write-Host ""
    
    $choice = Read-Host "是否繼續啟動前端？(y/n)"
    if ($choice -ne "y" -and $choice -ne "Y") {
        Write-Host "系統啟動已取消" -ForegroundColor Yellow
        Read-Host "按 Enter 鍵退出"
        exit 1
    }
}

Write-Host ""
Write-Host "🚀 啟動 FastAPI 後端服務..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "start_refactored_unified.py" -WindowStyle Minimized

Write-Host ""
Write-Host "⏳ 等待後端服務啟動..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "🚀 啟動前端演示服務器..." -ForegroundColor Yellow
Start-Process -FilePath "python" -ArgumentList "start_frontend_demo.py" -WindowStyle Minimized

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "✅ 系統啟動完成！" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📍 後端 API: http://localhost:8000" -ForegroundColor Cyan
Write-Host "🌐 前端界面: http://localhost:8080/frontend_glass.html" -ForegroundColor Cyan
Write-Host "📚 API 文檔: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 使用提示:" -ForegroundColor Yellow
Write-Host "1. 後端服務會在 http://localhost:8000 運行" -ForegroundColor White
Write-Host "2. 前端界面會在 http://localhost:8080 運行" -ForegroundColor White
Write-Host "3. 使用前端的'測試連線'按鈕檢查後端狀態" -ForegroundColor White
Write-Host "4. 選擇對話模式或表單模式開始使用" -ForegroundColor White
Write-Host ""
Write-Host "🔧 停止服務: 關閉對應的命令行窗口" -ForegroundColor Yellow
Write-Host ""

# 檢查後端狀態
Write-Host "🔍 檢查後端服務狀態..." -ForegroundColor Green
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ 後端服務狀態: 正常" -ForegroundColor Green
    }
    else {
        Write-Host "⚠️  後端服務狀態: 異常 (狀態碼: $($response.StatusCode))" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "❌ 後端服務狀態: 無法連線" -ForegroundColor Red
    Write-Host "請等待幾秒鐘後重試，或檢查後端服務是否正常啟動" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 系統啟動完成！請在瀏覽器中訪問前端界面開始使用。" -ForegroundColor Green
Write-Host "按任意鍵退出啟動器..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

