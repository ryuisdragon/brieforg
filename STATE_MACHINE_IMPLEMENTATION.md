# 狀態機硬控流程實現

## 1.3 變更總覽

### ✅ 新增：狀態機（硬控流程）

取代 LLM 自選題，永遠走同一條路。

#### 槽位定義

```typescript
type SlotKey =
  | "industry"
  | "objective"
  | "audience_targeting"
  | "campaign_theme"
  | "campaign_period"
  | "total_budget_twd"
  | "media_formats"
  | "plan_type";

const ORDER: SlotKey[] = [
  "industry",
  "objective",
  "audience_targeting",
  "campaign_theme",
  "campaign_period",
  "total_budget_twd",
  "media_formats",
  "plan_type",
];
```

#### 槽位檢查邏輯

```python
def is_slot_filled(slot_key: SlotKey, slots: ProjectSlots) -> bool:
    if slot_key == SlotKey.CAMPAIGN_PERIOD:
        return bool(slots.campaign_period and
                    slots.campaign_period.get('start') and
                    slots.campaign_period.get('end'))

    elif slot_key == SlotKey.TOTAL_BUDGET_TWD:
        return (isinstance(slots.total_budget_twd, int) and
                slots.total_budget_twd > 0)

    elif slot_key == SlotKey.MEDIA_FORMATS:
        return (isinstance(slots.media_formats, list) and
                len(slots.media_formats) > 0)

    else:
        value = getattr(slots, slot_key.value, None)
        if isinstance(value, list):
            return len(value) > 0
        return bool(value)
```

#### 下一個槽位邏輯

```python
def get_next_slot(slots: ProjectSlots) -> Union[SlotKey, str]:
    """獲取下一個需要填充的槽位"""
    for slot_key in SLOT_ORDER:
        if not is_slot_filled(slot_key, slots):
            return slot_key
    return "done"
```

### ✅ 3.1 欄位模型（覆寫）

#### 新增欄位

- `objective`（企劃目標）
- `sub_industry`（子產業/產品線，可選）

#### 變更欄位

- `total_budget_twd`（台幣單一數字）

#### 保持欄位

- `campaign_period = {start, end}`
- `media_formats` 限白名單（社群/搜尋/影音/OOH/KOL）

### ✅ 3.2 泡泡規格（替換）

泡泡固定在畫面底部，每輪 3–5 則，點一下就送。

不再有 adopt/refine。泡泡物件改為：

```python
class SuggestionBubble(BaseModel):
    label: str
    slot: SlotKey
    value: str
    send_as_user: str
```

### ✅ 5. Prompt 與輸出合約（整段替換 v1.1 的 JSON）

#### System（追加兩條硬規則）

1. 回覆正文必為兩句：① 根據輸入點出 1–3 個關鍵（名詞短語）② 用問句帶下一步；≤100 字。
2. 僅能就 nextSlot(slots) 的槽位出題：objective → audience → theme → period → budget…，不得亂跳。

#### Developer 輸出合約

```python
class StateMachineOutput(BaseModel):
    message: str = Field(..., max_length=100)  # 兩句洞察＋問句，≤100字
    next_question: str  # 問句式
    suggestions: List[SuggestionBubble]  # 3–5顆，點即送
    slot_writes: Optional[Dict[str, Any]]  # （可選）同步直寫
    rationale_cards: Optional[List[RationaleCard]]  # 只有在 theme 時必回
    missing_keys: List[str]  # 伺服端計算，用於待補欄位
    completion: float  # 完成度
```

#### 禁用字句

禁用"已成功提取專案資訊"類的客套話。

## 實現文件

### 1. 狀態機模型

- `models/state_machine_models.py` - 槽位定義和狀態機邏輯

### 2. 狀態機代理

- `agents/state_machine_agent.py` - 硬控流程代理實現

### 3. 狀態機提示詞

- `prompts/state_machine_prompts.py` - 固定流程提示詞

### 4. API 端點

- `api/routes.py` - 新增 `/chat/state-machine` 端點

## 使用方式

### 啟動狀態機聊天

```bash
POST /api/chat/state-machine
```

### 請求格式

```json
{
  "message": "用戶輸入",
  "session_id": "會話ID（可選）",
  "user_id": "用戶ID"
}
```

### 回應格式

```json
{
  "message": "兩句洞察＋問句，≤100字",
  "next_question": "問句式",
  "suggestions": [
    {
      "label": "建議標籤",
      "slot": "槽位鍵值",
      "value": "槽位值",
      "send_as_user": "發送給用戶的文字"
    }
  ],
  "slot_writes": {},
  "rationale_cards": [],
  "missing_keys": ["缺失的槽位"],
  "completion": 0.5
}
```

## 流程控制

1. **固定順序**: 嚴格按照 SLOT_ORDER 順序收集
2. **槽位驗證**: 每個槽位都有對應的驗證邏輯
3. **完成度計算**: 自動計算當前完成度
4. **建議生成**: 根據當前槽位生成對應的建議泡泡
5. **錯誤處理**: 備用回應機制，確保流程不中斷

## 優勢

1. **可預測性**: 用戶永遠知道下一步需要提供什麼信息
2. **一致性**: 所有用戶都走相同的流程
3. **效率**: 避免重複問題和無效對話
4. **完整性**: 確保收集到所有必要信息
5. **用戶體驗**: 清晰的進度指示和建議選項
