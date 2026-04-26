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
    "score_general": 数字,
    "score_specific": 数字,
    "score_total": 数字,
    "adjusted_score": 数字,
    "buffer_level": "无/黄色/橙色/红色",
    "buffer_deduction": 数字,
    "vetoed": false,
    "conclusion": "优秀/良好/中等/及格/不及格"
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
    {
      "clause_code": "G1",
      "clause_name": "首页规范性",
      "max_score": 4,
      "actual_score": 3,
      "evidence_position": "首页/教学目标部分",
      "judgment_text": "一句话说明"
    }
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
    "缓冲带判定=通过",
    "算术=通过",
    "高分复核=未触发/已完成",
    "低分复核=未触发/已完成"
  ],
  "strengths": ["优点1", "优点2"],
  "suggestions": ["建议1", "建议2"]
}

说明：
1. `conclusion` 必须是五档之一，不得输出“否决”。
2. 若存在高风险，仅通过 `buffer_level` 与 `buffer_deduction` 表达影响。
3. `adjusted_score = score_total - buffer_deduction`，最低不小于 0。
