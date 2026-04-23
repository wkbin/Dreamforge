# Output Schema

## Character Profile

```json
{
  "name": "人物名",
  "core_traits": ["性格1", "性格2"],
  "values": {
    "勇气": 0,
    "智慧": 0,
    "善良": 0,
    "忠诚": 0,
    "野心": 0,
    "正义": 0,
    "自由": 0,
    "责任": 0
  },
  "speech_style": "语言风格描述",
  "typical_lines": ["台词1"],
  "decision_rules": ["条件→反应"],
  "arc": {
    "start": {"勇气": 5},
    "mid": {"勇气": 6, "trigger_event": "事件"},
    "end": {"勇气": 7, "final_state": "状态"}
  },
  "evidence": {
    "descriptions": ["证据句"],
    "dialogues": ["证据句"],
    "thoughts": ["证据句"]
  },
  "confidence": 0.0
}
```

Rules:
- `core_traits` max 10 unique items.
- `typical_lines` max 8 unique items.
- `decision_rules` max 8 unique items.
- `values` all integers in `[0,10]`.
- `confidence` in `[0,1]`.

## Relations Graph

```json
{
  "林黛玉_贾宝玉": {
    "trust": 8,
    "affection": 9,
    "power_gap": 1,
    "conflict_point": "金玉良缘",
    "typical_interaction": "黛玉怼→宝玉哄→和好",
    "confidence": 0.0
  }
}
```

Rules:
- Relation key must be sorted lexicographically.
- `trust/affection` in `[0,10]`.
- `power_gap` in `[-5,5]`.
- `confidence` in `[0,1]`.

