"""
Scoring Controller V3.2
纯代码层评分控制器 —— 不依赖 LLM，所有规则硬编码。
职责：接收 LLM 原始输出 → 锚点校验 → 上限锁定 → TCI 修正 → 输出最终 adjusted_score。
"""

from typing import Any, Dict, List


def _safe_number(value: Any, default: float = 0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _conclusion_from_score(score: float) -> str:
    if score >= 90:
        return "优秀"
    if score >= 80:
        return "良好"
    if score >= 70:
        return "中等"
    if score >= 60:
        return "及格"
    return "不合格"


def _is_general_clause(clause_code: str) -> bool:
    """通用维度条款标识：以 G 开头（不区分大小写）。"""
    code = str(clause_code or "").strip().upper()
    return code.startswith("G")


def _is_specific_clause(clause_code: str) -> bool:
    """分项维度条款标识：以 S 开头（不区分大小写）。"""
    code = str(clause_code or "").strip().upper()
    return code.startswith("S")


# ──────────────────────────────────────────────
# 上限锁定规则配置
# ──────────────────────────────────────────────

# 关键词 → 触发的 ceiling 值
# ⚠️ 必须是精确匹配严重程度，避免误判轻微问题
CEILING_KEYWORDS = {
    55: [
        # 偏离临床实践（致命）
        "偏离临床实践", "纯基础研究", "纯理论", "纯基础", "有机合成",
        # 无教学过程/空壳（致命）
        "空壳教案", "无教学过程", "仅有标题无内容", "教学过程完全缺失",
    ],
    65: [
        # 教学目标完全不可测（严重）
        "完全不可测", "无任何行为动词", "行为动词完全缺失", "教学目标完全不可观察",
    ],
}


def detect_ceiling_from_issues(issues: List[Dict[str, Any]]) -> int:
    """
    扫描 issues 列表，检测是否触发分数上限锁定。
    返回最严格的 ceiling（最小值）；无触发则返回 100（表示无上限）。
    """
    ceiling = 100
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        sub = str(issue.get("issue_subcategory") or "").lower()
        text = str(issue.get("issue_text") or "").lower()
        cat = str(issue.get("issue_category") or "").lower()
        combined = f"{cat} {sub} {text}"

        for limit, keywords in CEILING_KEYWORDS.items():
            for kw in keywords:
                if kw in combined:
                    ceiling = min(ceiling, limit)
                    break  # 找到即跳出内层，继续下一个 limit
    return ceiling


# ──────────────────────────────────────────────
# Buffer（风险缓冲）计算规则
# ──────────────────────────────────────────────

def compute_buffer(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    根据 issues 严重程度计算 buffer_level 和 buffer_deduction。
    """
    fatal = sum(1 for i in issues if isinstance(i, dict) and i.get("severity") == "fatal")
    major = sum(1 for i in issues if isinstance(i, dict) and i.get("severity") == "major")

    if fatal > 0:
        return {"buffer_level": "红色", "buffer_deduction": 10}
    if major >= 3:
        return {"buffer_level": "橙色", "buffer_deduction": 5}
    if major >= 1:
        return {"buffer_level": "黄色", "buffer_deduction": 3}
    return {"buffer_level": "无", "buffer_deduction": 0}


# ──────────────────────────────────────────────
# TCI 修正规则
# ──────────────────────────────────────────────

def apply_tci_rules(tci: Dict[str, Any], current_ceiling: int) -> Dict[str, Any]:
    """
    应用 TCI 四级修正规则，返回 tci_deduction 和更新后的 ceiling。
    """
    tci_total = _safe_number(tci.get("total") if isinstance(tci, dict) else None)

    if tci_total >= 80:
        return {"tci_deduction": 0, "ceiling": current_ceiling}
    if 60 <= tci_total < 80:
        return {"tci_deduction": 10, "ceiling": current_ceiling}
    if 40 <= tci_total < 60:
        return {"tci_deduction": 0, "ceiling": min(current_ceiling, 60)}
    # TCI < 40
    return {"tci_deduction": 0, "ceiling": min(current_ceiling, 55)}


# ──────────────────────────────────────────────
# 核心入口
# ──────────────────────────────────────────────

def apply_scoring_rules(
    llm_score_general: float = 0,
    llm_score_specific: float = 0,
    llm_score_total: float = 0,
    llm_adjusted_score: float = 0,
    tci: Dict[str, Any] = None,
    issues: List[Dict[str, Any]] = None,
    vetoed: bool = False,
    buffer_level: str = "无",
    buffer_deduction: float = 0,
) -> Dict[str, Any]:
    """
    代码层评分控制器 —— 只做修正，不重算分数。

    LLM 已经正确算出 score_general + score_specific = score_total。
    本函数职责：
      1. 检测上限锁定（从 issues 关键词）
      2. 应用 TCI 修正（deduction / ceiling）
      3. 计算 buffer（风险缓冲扣分）
      4. 合成最终 adjusted_score 与结论

    返回:
        {
            'score_general': int,    # = LLM 原始值
            'score_specific': int,   # = LLM 原始值
            'score_total': int,      # = LLM 原始值
            'adjusted_score': int,   # 经代码层修正后
            'buffer_level': str,
            'buffer_deduction': int,
            'vetoed': bool,
            'conclusion': str,
        }
    """
    tci = tci or {}
    issues = issues or []

    # ── 1. 上限锁定（issues 检测）──
    ceiling = detect_ceiling_from_issues(issues)

    # ── 2. TCI 修正 ──
    tci_result = apply_tci_rules(tci, ceiling)
    ceiling = tci_result["ceiling"]
    tci_deduction = tci_result["tci_deduction"]

    # ── 3. Buffer 计算 ──
    buffer_info = compute_buffer(issues)
    # 如果 LLM 已经给了 buffer，以 LLM 为准；否则用代码层计算
    if buffer_level and buffer_level != "无":
        # LLM 已有判定，保持其值
        pass
    else:
        buffer_level = buffer_info["buffer_level"]
        buffer_deduction = buffer_info["buffer_deduction"]

    # ── 4. 合成 adjusted_score ──
    # 先用 LLM 的 adjusted_score，如果没有则用 score_total - deductions
    base_adjusted = llm_adjusted_score if llm_adjusted_score > 0 else llm_score_total
    adjusted_score = base_adjusted - buffer_deduction - tci_deduction
    adjusted_score = min(adjusted_score, ceiling)
    adjusted_score = max(0, int(adjusted_score))

    # ── 5. 结论 ──
    if vetoed:
        conclusion = "不合格"
    else:
        conclusion = _conclusion_from_score(adjusted_score)

    return {
        "score_general": int(llm_score_general),
        "score_specific": int(llm_score_specific),
        "score_total": int(llm_score_total),
        "adjusted_score": adjusted_score,
        "buffer_level": buffer_level,
        "buffer_deduction": int(buffer_deduction),
        "vetoed": bool(vetoed),
        "conclusion": conclusion,
    }
