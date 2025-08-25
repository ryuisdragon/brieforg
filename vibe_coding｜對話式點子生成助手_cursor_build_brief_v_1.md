# VibeCoding｜對話式點子生成助手 Cursor Build Brief v1.1（Ryu 定制）

> 目的：將「能對話引導用戶輸入並給出點子」的 AI Chat 專案助手，轉成可落地的規格與可實作的任務清單，提供 Cursor 執行。

---

## 1. 核心目標與非目標

**核心目標**

1. 作為「業務, 客戶, 企劃」之間的橋樑, 讓新手業務能像老鳥一樣問全套重點, 聚焦媒體廣告產業, 依客戶產業動態調整提問。
2. 以對話方式逐步收集欄位, 每輪回覆正文不超過一百字, 保留人味, 專業親切, 不灌長文。
3. 每句對話產出三到五個動態建議泡泡, 方便點擊採納或細化, 減少複製貼上。
4. 右側即時預覽 Brief, 僅寫入已確認的決定, 顯示未填欄位, 進度條同步更新。
5. 完成度達九十五分時, 生成完整企劃專案, 含 Markdown 提案骨架與可複製大綱。

**非目標**

1. 不進行外部真實查詢, 只提供搜尋式與檢核清單。
2. 不做媒體排期與預算自動最佳化, 聚焦發想與結構。
3. 不產生超過一百字的長段回覆, 泡泡與預覽更新不計入字數。

---

## 2. 使用者情境與故事

- 新手 Planner 想快速把「品牌痛點」與「活動主題」整理成骨架。
- 資深 PM 想用對話把散亂想法收斂成簡報大綱。
- 創意夥伴需要三個方向的標語與概念標題，並想保留修改歷史。

**成功定義** 用戶在十回合內，完成七成以上欄位，得到一份可直接貼進 Notion 與 PPT 的結構稿。

---

## 3. 核心互動規格

**3.1 欄位模型（Slots）** 必填欄位

- industry（產業）
- campaign\_theme（活動主題）
- proposal\_due\_date（提案交付日期）
- campaign\_period（活動期間, 物件含 start 與 end）
- total\_budget（專案總預算）
- media\_formats（投放形式, 例如 社群, 搜尋, OOH）
- plan\_type（企劃類型, 例如 策略提案, 創意版位, 文案）
- audience\_targeting（目標受眾）

選填欄位

- audience\_behavior（受眾行為分析）
- client\_assets（客戶素材）
- client\_requirements（客戶要求）
- tech\_requirements（技術需求）
- risks（風險評估）
- next\_steps（後續步驟）

**3.2 提示泡泡（Suggestions Bar）**

- 每輪產出三到五則, 僅文字, 簡潔可讀, 例如「家庭親子客」, 「年輕族群」, 「教育單位」。
- UI 顯示僅文字與兩個按鈕, 採納與細化, Slot 標註僅在內部使用。
- 泡泡內容隨每句對話即時更新, 與當前追問語意一致。

**3.3 右側預覽（Preview Pane）**

- 上方為 Brief 區塊, 欄位依序為 產業, 活動主題, 提案交付時間, 活動期間, 預算, 投放形式, 企劃類型, 受眾鎖定, 受眾行為分析, 客戶素材, 客戶要求, 技術需求, 風險評估, 後續步驟。
- 顯示已填值與未填提示, 僅寫入已採納或用戶明確輸入的內容。
- 下方顯示完成度進度條。

**3.4 完成度指標（Completion Meter）**

- 欄位權重, industry 10, campaign\_theme 15, proposal\_due\_date 5, campaign\_period 10, total\_budget 10, media\_formats 10, plan\_type 10, audience\_targeting 15, audience\_behavior 5, client\_assets 2, client\_requirements 3, tech\_requirements 3, risks 1, next\_steps 1。
- 完成度達九十五分時解鎖完整企劃專案生成。

**3.5 報告生成**

- 兩段式輸出, Brief Markdown 與 Full Plan Markdown, 同步輸出對應 JSON。
- Full Plan 採以下模板, 與右側欄位對應。

```md
## 📋 專案概覽
**活動名稱**:
**產業類別**:
**緊急程度**:

## ⏰ 時程與預算
**提案交付日期**:
**活動開始日期**:
**活動結束日期**:
**專案總預算**:

## 🎯 內容與策略
**企劃類型**:  **投放形式**:
**目標受眾**:
**受眾行為分析**:

## 📦 客戶資源
**客戶素材**:
**客戶要求**:

## 🔧 技術需求

## 📊 提案內容

### 市場洞察

### 競品分析

### 策略提案

### 媒體規劃

### 預算及預估成效

### 時程規劃

### 技術需求

### 風險評估

### 後續步驟
```

---

## 4. 對話流程示例（精簡版）

1. 用戶：你好
2. 助手：我先幫你定骨架，我需要知道你的主要目標與受眾。你想先說哪一個（建議泡泡：設定主要目標，定義受眾）
3. 用戶點「設定主要目標」
4. 助手：常見的目標有提升品牌知名度，帶動試用，促成名單。你比較像哪一類，或你有更精準的說法
5. 用戶輸入「促成試用與名單」
6. 助手寫回 objective，更新完成度，產生下一輪建議泡泡，並於預覽顯示「目標：促成試用與名單」。

---

## 5. Prompt Scaffold（會話引擎）

**System** 你是媒體廣告產業的對話式專案助手, 使用者是業務。你的任務是協助釐清個案資訊並填滿 Slots, 每輪回覆正文不超過一百字, 親切專業, 不囉嗦。避免自作主張, 僅在用戶確認或採納泡泡後寫入欄位。嚴禁捏造數據與競品資料。

**Developer 指令與輸出合約** 請輸出 JSON, 嚴格遵守鍵名與型別。

```json
{
  "next_question": "string",
  "suggestions": [{ "text": "string", "action": "adopt|refine", "slot": "industry|campaign_theme|proposal_due_date|campaign_period|total_budget|media_formats|plan_type|audience_targeting|audience_behavior|client_assets|client_requirements|tech_requirements|risks|next_steps" }],
  "slot_writes": { "industry": "string", "campaign_theme": "string", "proposal_due_date": "string", "campaign_period": {"start":"string","end":"string"}, "total_budget": "string", "media_formats": ["string"], "plan_type": "string", "audience_targeting": ["string"], "audience_behavior": "string", "client_assets": ["string"], "client_requirements": ["string"], "tech_requirements": ["string"], "risks": ["string"], "next_steps": ["string"] },
  "preview_blocks": [{ "id": "industry", "title": "產業", "content": "string" }],
  "completion": 0
}
```

**Few-shot 規則**

- 當用戶只打招呼時, 先鎖產業或活動主題兩個入口。
- 當用戶概念模糊, 先給方向型泡泡, 例如三種受眾或三種投放形式。
- 泡泡必須與上一句對話強相關, 不可復讀。

---

## 6. 前端規格（React 或任意支援 TS 的框架均可）

**畫面區塊**

- 左上, 進度條與未填欄位提示, 可點擊跳到對應追問。
- 左中, 對話區, 單輪訊息, AI 正文不超過一百字。
- 左下, 動態建議泡泡列, 三到五則, 採納或細化。
- 右上, Brief 預覽, 逐欄位顯示與標註未填。
- 右下, Full Plan 視窗占位, 當完成度達九十五分時顯示生成按鈕與預覽。

**核心組件**

- ChatPane, SuggestionBar, BriefPreview, ProgressPanel, FullPlanModal。

**全域狀態 Shape** 維持既有結構, Slots 與欄位名稱依 3.1 更新。

**互動規則**

- 採納泡泡即寫入 Slots, 並回一則簡短確認。
- 細化會以該泡泡文本作為下一輪 user content。

---

## 7. 後端 API 合約

**POST /api/chat** 請求

```json
{ "messages": [{"role":"user","content":"string"}], "slots": {"industry":"string"}, "history_limit": 8 }
```

回應

```json
{ "next_question":"string", "suggestions":[{"text":"string","action":"adopt","slot":"industry"}], "slot_writes": {"industry":"string"}, "preview_blocks": [{"id":"industry","title":"產業","content":"string"}], "completion": 55 }
```

**POST /api/report** 請求

```json
{ "slots": {"industry":"string"}, "preview": [{"id":"industry","title":"產業","content":"string"}] }
```

回應

```json
{ "brief_markdown":"string", "full_markdown":"string", "json": {"slots": {}, "outline": {} } }
```

---

## 8. 資料模型與持久化

- 支援本地快照與復原, 提供版本紀錄與回滾。
- Session, Message, Snapshot 結構沿用, 另加 Version 表格記錄生成的 Brief 與 Full Plan。

---

## 9. 事件追蹤與量測

- 需追蹤, message\_sent, suggestion\_adopted, field\_autofill, threshold\_reached, brief\_generated, fullplan\_generated, error\_shown。

---

## 10. 邊界與錯誤處理

- 模型回傳不合約時, 以容錯解析可用鍵, 其他忽略並在對話中顯示「我剛剛抓不到重點, 幫我改寫更精簡」, 同步顯示錯誤提示。
- 偵測連續重複建議或追問, 啟動去重與改寫策略, 避免跳針。
- 未填欄位過多時, 提供導覽列出三個最關鍵欄位入口。

---

## 11. 驗收標準與測試案例

**核心標準**

1. 單輪回覆正文不超過一百字。
2. 每輪泡泡三到五則且與對話強相關, 採納後立即更新 Brief 與完成度。
3. 完成度達九十五, 顯示生成完整企劃按鈕, 可輸出 Brief 與 Full Plan Markdown 與 JSON。

**測試案例補充**

- Case E 行業切換, 用戶輸入新產業時, 泡泡與追問應改以新產業語境生成。
- Case F 跳針防護, 模型重複問同題三次時, 客製錯誤訊息出現並改寫追問。

---

## 12. 給 Cursor 的實作任務清單

1. 依本版本欄位與 UI 區塊建立前端骨架, 完成進度條與未填欄位提示。
2. 串接本地 Ollama 模型供應器, 預設 gemma3:27b, 包裝輸出合約與字數限制。
3. 完成完成度計算與九十五分解鎖邏輯。
4. 撰寫整合測試, 覆蓋核心標準與 Case E, Case F。

---

## 13. 參考程式骨架片段

**Ollama 呼叫樣例, Node**

```ts
const resp = await fetch('http://localhost:11434/api/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    model: 'gemma3:27b',
    prompt: systemAndUserPrompt,
    stream: false
  })
})
const text = await resp.text()
```

**字數裁切輔助**

```ts
export function clampReply(txt: string, limit = 100) {
  const s = txt.replace(/
/g, ' ').trim()
  return s.length <= limit ? s : s.slice(0, limit)
}
```

**完成度計算, 依新權重**

```ts
export function computeCompletion(slots: any): number {
  let score = 0
  if (slots.industry) score += 10
  if (slots.campaign_theme) score += 15
  if (slots.proposal_due_date) score += 5
  if (slots.campaign_period?.start && slots.campaign_period?.end) score += 10
  if (slots.total_budget) score += 10
  if (slots.media_formats?.length) score += 10
  if (slots.plan_type) score += 10
  if (slots.audience_targeting?.length) score += 15
  if (slots.audience_behavior) score += 5
  if (slots.client_assets?.length) score += 2
  if (slots.client_requirements?.length) score += 3
  if (slots.tech_requirements?.length) score += 3
  if (slots.risks?.length) score += 1
  if (slots.next_steps?.length) score += 1
  return Math.min(score, 100)
}
```

---

## 14. 報告輸出樣板

已於 3.5 節提供 Full Plan Markdown 範本, 另提供 JSON 映射供串接。

---

## 15. 後續擴充路線

- 產業語感模板庫, 預設媒體廣告業, 客戶產業以可插拔詞庫覆寫。
- 多語輸出, 中英切換。
- 版型管理, 依不同提案型態切換 Full Plan 章節組合。

---

## 16. Cursor 任務提示（可直接貼）

依 1.1 版規格建立專案, 完成對話流, 泡泡列, Brief 預覽與進度條。串接 Ollama gemma3:27b, 輸出合約遵循第 5 節 JSON 結構, 每輪正文不超過一百字。完成九十五分解鎖並輸出 Brief 與 Full Plan。提供測試錄影與測試碼。

