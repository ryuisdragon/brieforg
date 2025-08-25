# 🎯 企劃需求助手 - 統一模組化架構

一個智能的企劃專案管理和受眾分析系統，採用**統一模組化架構**設計，提供流暢的對話式需求收集體驗。

## 🚀 核心特色

### ✨ 統一對話入口

- **單一端點**：`POST /chat/turn` 處理所有對話需求
- **智能路由**：自動判斷下一步行動（提問、分析、策略生成）
- **上下文感知**：基於專案狀態提供相關建議

### 🧠 AI 驅動的智能分析

- **自動需求提取**：從自然語言中提取結構化專案資訊
- **受眾洞察生成**：深度分析目標受眾特徵和行為
- **內容策略建議**：基於專案目標提供投放策略
- **完整性評估**：實時評估專案資訊的完整度

### 💬 後端驅動的 UI

- **動態選項生成**：AI 驅動的上下文相關選項
- **實時專案預覽**：即時顯示專案進度和狀態
- **智能快速回覆**：基於專案狀態的個性化建議

## 🏗️ 模組化架構

```
├── models/                          # 統一數據模型
│   ├── unified_models.py           # 核心數據模型
│   ├── audience_models.py          # 受眾分析模型
│   ├── base_models.py              # 基礎模型
│   ├── chat_models.py              # 聊天模型
│   └── project_models.py           # 專案模型
├── prompts/                         # 提示詞管理
│   └── unified_prompts.py          # 統一提示詞系統
├── tools/                           # 工具執行器
│   └── unified_tools.py            # 統一工具管理
├── agents/                          # 智能代理
│   └── unified_planning_agent.py   # 統一規劃代理
├── services/                        # 核心服務
│   ├── unified_session_manager.py  # 統一會話管理
│   └── llm_client.py               # LLM 客戶端
├── api/                             # API 路由
│   ├── routes.py                   # 主要路由
│   └── options_routes.py           # 選項路由
├── app_refactored_unified.py       # 主應用程式
├── start_refactored_unified.py     # 啟動腳本
├── frontend_unified.html           # 統一前端界面
└── REFACTORING_COMPLETE_SUMMARY.md # 重構完成總結
```

## 🛠️ 技術棧

- **後端框架**：FastAPI + Python 3.8+
- **AI 模型**：Ollama (gemma3:27b)
- **前端技術**：原生 JavaScript + CSS3 (玻璃擬態設計)
- **數據驗證**：Pydantic
- **會話管理**：統一會話管理器 + 本地持久化

## 📦 快速啟動

### 1. 環境要求

- Python 3.8+
- Ollama 服務
- 現代瀏覽器

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 啟動服務（新架構入口）

```bash
uvicorn app_refactored_unified:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 訪問界面

- **前端界面**：`frontend_glass.html`
- **API 文檔**：`http://localhost:8000/docs`
- **健康檢查**：`http://localhost:8000/health`

## 🌐 API 端點

### 核心對話

- `POST /chat/turn` - 統一對話端點（新架構）

### 會話管理

- `GET /chat/sessions` - 會話列表
- `GET /chat/sessions/{session_id}` - 會話詳情
- `DELETE /chat/sessions/{session_id}` - 刪除會話
- `POST /chat/sessions/{session_id}/close` - 關閉會話
- `POST /chat/sessions/{session_id}/reset` - 重置會話

### 專案管理

- `GET /chat/sessions/{session_id}/project` - 獲取專案數據
- `PUT /chat/sessions/{session_id}/project` - 更新專案數據
- `GET /chat/sessions/{session_id}/history` - 獲取對話歷史

### 系統狀態

- `GET /health` - 健康檢查（UTC 時間戳、llm_reachable）
- `GET /models` - 可用模型列表
- `GET /stats` - 系統統計
- `GET /cleanup` - 清理過期會話

## 🎯 使用流程

### 1. 開始對話

在對話框中描述您的專案需求，例如：

> "我想為動物園做一個行銷活動"

### 2. 智能引導

系統會自動：

- 提取專案資訊
- 識別缺失欄位
- 生成相關問題
- 提供選項建議

### 3. 快速選擇

點擊系統提供的選項按鈕，快速補充專案資訊

### 4. 實時預覽

右側面板實時顯示：

- 專案完整度
- 已收集資訊
- 缺失項目

### 5. 完成專案

系統會自動生成：

- 受眾洞察分析
- 內容策略建議
- 投放建議

## 🔧 核心模組

### UnifiedPlanningAgent

統一的規劃代理，負責：

- 對話流程控制
- 智能路由決策
- 工具調度管理

### ToolExecutor

工具執行器，提供：

- 受眾洞察生成
- 快速回覆生成
- 完整性評估
- 內容策略生成

### UnifiedSessionManager

統一會話管理器，負責：

- 會話生命週期管理
- 數據持久化
- 狀態同步

### LLMClient

LLM 客戶端，提供：

- 統一的 AI 模型調用
- 錯誤處理和重試
- 響應格式標準化

## 📊 重構成果

| 方面         | 重構前         | 重構後                  |
| ------------ | -------------- | ----------------------- |
| **API 端點** | 15+ 個分散端點 | 1 個統一端點 + 管理端點 |
| **會話管理** | 3 套獨立系統   | 1 套統一系統            |
| **代理邏輯** | 2 個獨立代理   | 1 個統一代理            |
| **代碼結構** | 單體 3800 行   | 模組化 8 個檔案         |
| **前端邏輯** | 寫死的選項     | 後端驅動的動態選項      |
| **數據模型** | 分散的模型     | 統一的整合模型          |

## 🚀 開發指南

### 添加新功能

1. 在對應模組中添加功能邏輯
2. 在 `unified_tools.py` 中註冊新工具
3. 更新 `unified_models.py` 中的數據模型
4. 測試新功能的整合

### 擴展 API

1. 在 `app_refactored_unified.py` 中添加新端點
2. 更新相關的數據模型
3. 添加錯誤處理和驗證

### 自定義提示詞

1. 在 `unified_prompts.py` 中添加新提示詞
2. 在對應的工具中調用新提示詞
3. 測試提示詞的效果

## 📝 更新日誌

### v2.0.0 (統一模組化架構)

- ✅ 統一對話入口：單一 `/chat/turn` 端點（請勿再啟舊 `app:app`）
- ✅ 統一會話管理：整合專案和受眾數據
- ✅ 統一代理系統：`UnifiedPlanningAgent` 總控制器
- ✅ 模組化架構：8 個職責明確的模組
- ✅ 後端驅動 UI：AI 驅動的動態選項生成
- ✅ 實時專案預覽：完整的狀態管理和視覺化

### v1.x.x (原始版本)

- 基礎的企劃需求收集
- 受眾教練功能
- 單體式架構

## 🤝 貢獻指南

1. Fork 本專案
2. 創建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 📄 授權條款

本專案採用 MIT 授權條款 - 詳見 [LICENSE](LICENSE) 文件

## 📞 聯繫方式

如有問題或建議，請開啟 Issue 或聯繫開發團隊。

---

**注意**：本系統需要 Ollama 服務和 gemma3:27b 模型才能正常運行。請確保在啟動前已正確配置 AI 環境。

詳細的重構過程和技術細節，請參考 [REFACTORING_COMPLETE_SUMMARY.md](REFACTORING_COMPLETE_SUMMARY.md)。
