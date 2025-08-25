# 企劃需求助手 - 前端整合指南

## 概述

這是一個完整的企劃需求助手系統，包含：

- **後端**: FastAPI 服務，提供企劃分析和對話管理
- **前端**: 玻璃擬態設計的現代化 Web 界面
- **功能**: 對話模式和表單模式兩種使用方式

## 系統架構

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端界面      │    │   FastAPI       │    │   Ollama        │
│  (Glass UI)     │◄──►│   後端服務      │◄──►│   LLM 服務      │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 快速開始

### 1. 啟動後端服務

```bash
# 啟動 Ollama 服務（如果還沒啟動）
ollama serve

# 啟動 FastAPI 後端
python start_refactored_unified.py
```

後端將在 `http://localhost:8000` 運行

### 2. 使用前端

直接在瀏覽器中打開 `frontend_glass.html` 文件，或使用簡單的 HTTP 服務器：

```bash
# Python 3
python -m http.server 8080

# 或使用 Node.js
npx serve .

# 然後訪問 http://localhost:8080/frontend_glass.html
```

## 功能特性

### 🗣️ 對話模式

- 自然語言對話
- 智能問答引導
- 即時專案資訊更新
- 完整度追蹤

### 📝 表單模式

- 快速需求輸入
- 預設範本選擇
- 需求分析與評估
- 缺失欄位識別

### 📊 即時預覽

- 專案資訊彙整
- 完整度進度條
- 待補欄位提示
- 企劃提案草稿

## API 端點

### 核心端點

- `POST /chat/turn` - 對話回合處理
- `GET /health` - 健康檢查
- `GET /models` - 可用模型列表

### 新增端點

- `POST /analyze/requirement` - 需求分析
- `POST /analyze/clarify` - 澄清處理

### 會話管理

- `GET /chat/sessions` - 列出會話
- `GET /chat/sessions/{id}` - 獲取會話詳情
- `DELETE /chat/sessions/{id}` - 刪除會話
- `POST /chat/sessions/{id}/close` - 關閉會話
- `POST /chat/sessions/{id}/reset` - 重置會話

## 前端功能詳解

### 1. 玻璃擬態設計

- 現代化的視覺效果
- 響應式佈局
- 流暢的動畫過渡
- 優雅的陰影和模糊效果

### 2. 雙模式切換

- **對話模式**: 適合逐步完善需求
- **表單模式**: 適合快速分析和評估

### 3. 智能提示

- 完整性進度條
- 缺失欄位標籤
- 即時預覽更新
- 狀態指示器

### 4. 快速範本

- 淨水器品牌知名度提升
- 眼鏡品牌市場分析
- 科技新品上市
- 簡單企劃需求

## 使用流程

### 對話模式流程

1. 用戶輸入初始需求
2. AI 分析並提出問題
3. 用戶回答問題
4. 系統更新專案資訊
5. 重複直到完成
6. 生成完整企劃提案

### 表單模式流程

1. 輸入或選擇需求描述
2. 點擊「分析需求」
3. 查看分析結果
4. 補充澄清資訊（可選）
5. 查看完整度評估

## 技術細節

### 前端技術

- HTML5 + CSS3
- 原生 JavaScript (ES6+)
- CSS Grid 和 Flexbox
- CSS 變數和動畫
- 響應式設計

### 後端技術

- FastAPI (Python)
- Pydantic 數據驗證
- 異步處理
- 會話管理
- LLM 整合

### 數據模型

- 專案屬性 (ProjectAttributes)
- 時間預算 (TimeBudget)
- 內容策略 (ContentStrategy)
- 技術需求 (TechnicalNeeds)
- 受眾洞察 (AudienceInsights)

## 配置選項

### 後端配置

```python
# config.py
FASTAPI_HOST = "0.0.0.0"
FASTAPI_PORT = 8000
OLLAMA_BASE_URL = "http://localhost:11434"
```

### 前端配置

```javascript
// 在 frontend_glass.html 中
const api = document.getElementById("api");
api.value = "http://localhost:8000"; // 預設 API 地址
```

## 故障排除

### 常見問題

1. **連線失敗**

   - 檢查 Ollama 服務是否運行
   - 確認 FastAPI 後端端口
   - 檢查防火牆設置

2. **前端無法載入**

   - 使用 HTTP 服務器而非直接打開文件
   - 檢查瀏覽器控制台錯誤
   - 確認 CORS 設置

3. **API 錯誤**
   - 檢查後端日誌
   - 確認模型是否可用
   - 驗證請求格式

### 日誌查看

```bash
# 查看後端日誌
tail -f app.log

# 查看 Ollama 日誌
ollama logs
```

## 開發指南

### 添加新功能

1. 在 `models/` 中定義數據模型
2. 在 `services/` 中實現業務邏輯
3. 在 `app_refactored_unified.py` 中添加 API 端點
4. 在前端添加對應的 UI 組件

### 自定義樣式

- 修改 CSS 變數來調整主題
- 調整玻璃擬態效果的參數
- 自定義動畫和過渡效果

### 擴展模型

- 在 `models/unified_models.py` 中添加新欄位
- 更新完整度計算邏輯
- 調整前端顯示邏輯

## 性能優化

### 前端優化

- 使用 CSS 硬體加速
- 優化動畫性能
- 減少 DOM 操作

### 後端優化

- 異步處理請求
- 會話數據緩存
- LLM 響應優化

## 安全考慮

- 輸入驗證和清理
- 會話隔離
- 錯誤訊息處理
- CORS 配置

## 部署建議

### 生產環境

- 使用 HTTPS
- 配置反向代理 (Nginx)
- 設置日誌輪轉
- 監控和警報

### Docker 部署

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "start_refactored_unified.py"]
```

## 貢獻指南

1. Fork 項目
2. 創建功能分支
3. 提交更改
4. 發起 Pull Request

## 授權

本項目採用 MIT 授權條款

## 聯繫方式

如有問題或建議，請提交 Issue 或聯繫開發團隊。

---

**注意**: 確保在啟動完整系統前，Ollama 服務和 FastAPI 後端都已正確運行。

