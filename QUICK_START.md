# 🚀 快速開始指南

## 一鍵啟動系統

### Windows 用戶

```bash
# 方法1: 雙擊執行
start_system.bat

# 方法2: PowerShell (推薦)
.\start_system.ps1

# 方法3: 手動啟動
start_system.bat
```

### 手動啟動步驟

```bash
# 1. 啟動 Ollama 服務
ollama serve

# 2. 啟動後端服務 (新開一個終端)
python start_refactored_unified.py

# 3. 啟動前端服務 (新開一個終端)
python start_frontend_demo.py
```

## 訪問地址

- **前端界面**: http://localhost:8080/frontend_glass.html
- **後端 API**: http://localhost:8000
- **API 文檔**: http://localhost:8000/docs

## 快速測試

1. 打開前端界面
2. 點擊「測試連線」按鈕
3. 選擇「對話模式」或「表單模式」
4. 開始使用！

## 常見問題

### Q: 端口被占用怎麼辦？

A: 修改啟動腳本中的端口號，或關閉占用端口的程序

### Q: 後端無法連線？

A: 確保 Ollama 服務正在運行，檢查防火牆設置

### Q: 前端無法載入？

A: 使用 HTTP 服務器而非直接打開 HTML 文件

## 需要幫助？

查看詳細文檔：`FRONTEND_INTEGRATION_README.md`

