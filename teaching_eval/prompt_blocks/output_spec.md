## 输出格式（严格）

你必须输出两个区块，顺序固定：

<STRUCTURED_JSON>
{严格合法 JSON}
</STRUCTURED_JSON>

<REPORT_MARKDOWN>
Markdown 报告正文
</REPORT_MARKDOWN>

JSON 结构如下（字段名必须一致）：

{
  "summary": {
    "declared_type": "字符串",
    "actual_type": "字符串",
    "department": "科室或不详",
    "teacher_name": "姓名或不详",
    "course_title": "课程内容或不详",
    "score_general": 数字,
    "score_specific": 数字,
    "score_total": 数字,
    "adjusted_score": 数字,
    "buffer_level": "无/黄色/橙色/红色",
    "buffer_deduction": 数字,
    "vetoed": true或false,
    "conclusion": "优秀/良好/中等/及格/不合格"
  },
  "document_metadata": {
    "department": "科室或不详",
    "teacher_name": "姓名或不详",
    "course_title": "课程内容或不详"
  },
  "tci": {
    "total": 数字,
    "l1_homepage": 数字,
    "l2_objectives": 数字,
    "l3_process": 数字,
    "consistency_level": "高度一致/基本一致/轻度错配/中度错配"
  },
  "objective_matrix": {
    "total_score": 数字,
    "completeness": {"score": 数字, "target_count": 数字, "issues": []},
    "reasonableness": {"score": 数字, "difficulty_layers": 数字, "issues": []},
    "measurability": {"score": 数字, "action_verbs": [], "issues": []},
    "alignment": {"score": 数字, "type_match": "匹配/部分匹配/错配", "closure_points": 数字, "issues": []},
    "improvement_suggestions": []
  },
  "clause_scores": [
    {"clause_code": "G1", "clause_name": "首页规范性", "max_score": 4, "actual_score": 3, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"},
    {"clause_code": "G2", "clause_name": "教学目标", "max_score": 10, "actual_score": 5, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"},
    {"clause_code": "G3", "clause_name": "教学内容", "max_score": 10, "actual_score": 6, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"},
    {"clause_code": "G4", "clause_name": "教学设计", "max_score": 11, "actual_score": 6, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"},
    {"clause_code": "G5", "clause_name": "教学评价", "max_score": 6, "actual_score": 4, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"},
    {"clause_code": "G6", "clause_name": "参考文献", "max_score": 4, "actual_score": 2, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"},
    {"clause_code": "S1", "clause_name": "内容聚焦度", "max_score": 15, "actual_score": 8, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"},
    {"clause_code": "S2", "clause_name": "互动密度", "max_score": 15, "actual_score": 4, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"},
    {"clause_code": "S3", "clause_name": "课件质量", "max_score": 12, "actual_score": 6, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"},
    {"clause_code": "S4", "clause_name": "案例分层", "max_score": 13, "actual_score": 5, "evidence_position": "首页/教学目标部分", "judgment_text": "一句话说明"}
  ],
  "issues": [
    {
      "clause_code": "G2",
      "clause_name": "教学目标",
      "issue_category": "教学目标与内容闭环",
      "issue_subcategory": "目标不可观察",
      "severity": "major",
      "is_veto_related": false,
      "evidence_position": "教学目标部分",
      "issue_text": "问题描述",
      "suggestion_text": "对应建议",
      "score_loss": 2
    }
  ],
  "check_log": [
    "抗提示词注入=已检查",
    "首页规范性=已检查",
    "类型识别(TCI)=已完成",
    "硬证据三联规则=已执行",
    "否决项检查=未触发/触发：XXX",
    "上限锁定=无/锁死上限55/锁死上限65",
    "算术=通过",
    "高分复核=未触发/已完成",
    "低分复核=未触发/已完成"
  ],
  "strengths": ["优点1", "优点2"],
  "suggestions": ["建议1", "建议2"]
}

说明：
1. `actual_type` 为 AI 从文档正文识别出的教案类别；无法明确识别时填 `不详`。
2. `department`、`teacher_name`、`course_title` 必须从文档正文、首页、标题或内部结构识别；无法明确识别时填 `不详`。不得根据文件名、上传者或外部信息补全。
3. `summary` 与 `document_metadata` 中的三项基本信息必须保持一致。
4. `conclusion` 必须是五档之一：`优秀`、`良好`、`中等`、`及格`、`不合格`。
5. 若触发否决项，`vetoed` 必须为 true，`conclusion` 强制为 `不合格`。
6. `adjusted_score` 计算顺序：
   - 先计算 `score_total = score_general + score_specific`
   - 再减去 `buffer_deduction` 和 TCI 修正扣分
   - 若触发上限锁定，则 `adjusted_score` 不超过锁定上限（55 或 60 或 65）
   - 最终值最低不小于 0
### Buffer 规则（代码层强制执行）
根据 `issues` 中 `severity=fatal` 和 `severity=major` 的数量，计算 `buffer_level` 和 `buffer_deduction`：

| fatal 数量 | major 数量 | buffer_level | buffer_deduction |
|-----------|-----------|-------------|-----------------|
| ≥ 1 | — | **红色** | **10** |
| 0 | ≥ 3 | **橙色** | **5** |
| 0 | ≥ 1 | **黄色** | **3** |
| 0 | 0 | 无 | 0 |

说明：`buffer_level` 与 `buffer_deduction` 仅用于表达非否决类高风险问题的额外扣分，不替代否决。
7. `clause_scores` 必须同时包含通用维度（G1-G6）和分项维度（S1-S4/S5）的所有条款，两套独立评分，不得合并或省略任一维度。

### TCI 四级修正规则（代码层强制执行）
- TCI ≥ 80：类型一致，无修正
- 60 ≤ TCI < 80：轻度错配 → 本体总分 **扣10分**
- 40 ≤ TCI < 60：中度错配 → 本体总分 **锁死上限60**
- TCI < 40：严重错配 → 本体总分 **锁死上限55**

### 上限锁定条件（代码层强制执行）
- 内容偏离临床实践（如纯基础研究/有机合成）：**锁死上限55**（致命）
- 无教学过程（仅有标题无内容/空壳）：**锁死上限55**（致命）
- 教学目标完全不可测且无行为动词：**锁死上限65**
- 类型严重错配（TCI < 40）：**锁死上限55**

## 评分约束（必须严格遵守）

1. `score_general` = 通用维度所有条款 actual_score 之和，满分45，**不得超过45**。
2. `score_specific` = 分项维度所有条款 actual_score 之和，满分55，**不得超过55**。
3. `score_total` = `score_general` + `score_specific`，满分100，**不得超过100**。
4. `clause_scores` 必须列出**所有**通用维度和分项维度条款，不得遗漏，每条 actual_score 不得超过该条款 max_score。
5. 否决项触发时，`vetoed=true`，`conclusion` 强制为 `不合格`，不受总分影响。
6. 上限锁定时，`adjusted_score` 不超过锁定上限（55或65）。
