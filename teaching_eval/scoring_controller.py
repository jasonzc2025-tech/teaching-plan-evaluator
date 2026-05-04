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


def _clamp(value: Any, minimum: float, maximum: float) -> float:
    return max(minimum, min(_safe_number(value), maximum))


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _contains_any(text: str, needles: List[str]) -> bool:
    return any(_norm(needle) and _norm(needle) in text for needle in needles)


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

# 上限锁定不直接扫全文，只接受 issues 中已经被 LLM 归类为严重问题的条目。
# 每条规则同时校验严重程度、问题分类/子类和关键词，避免“纯基础理论扎实”之类的褒义语境误触发。
CEILING_RULES = [
    {
        "limit": 55,
        "severities": {"fatal"},
        "categories": ["临床实践", "内容偏离", "教学内容偏离"],
        "subcategories": ["偏离临床实践", "内容偏离", "纯基础研究"],
        "keywords": ["偏离临床实践", "纯基础研究", "纯理论", "纯基础", "有机合成"],
    },
    {
        "limit": 55,
        "severities": {"fatal"},
        "categories": ["教学设计与流程", "教学过程", "空壳教案"],
        "subcategories": ["无教学过程", "空壳教案", "教学过程缺失"],
        "keywords": ["空壳教案", "无教学过程", "仅有标题无内容", "教学过程完全缺失"],
    },
    {
        "limit": 65,
        "severities": {"major", "fatal"},
        "categories": ["教学目标", "目标"],
        "subcategories": ["目标不可测", "行为动词缺失", "不可观察"],
        "keywords": ["完全不可测", "无任何行为动词", "行为动词完全缺失", "教学目标完全不可观察"],
    },
]


def _matches_ceiling_rule(issue: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    severity = _norm(issue.get("severity"))
    if severity not in rule["severities"]:
        return False

    cat = _norm(issue.get("issue_category"))
    sub = _norm(issue.get("issue_subcategory"))
    text = _norm(issue.get("issue_text"))
    evidence = f"{sub} {text}"

    if not _contains_any(evidence, rule["keywords"]):
        return False
    return _contains_any(cat, rule["categories"]) or _contains_any(sub, rule["subcategories"])


def detect_ceiling_from_issues(issues: List[Dict[str, Any]]) -> int:
    """
    扫描 issues 列表，检测是否触发分数上限锁定。
    返回最严格的 ceiling（最小值）；无触发则返回 100（表示无上限）。
    """
    ceiling = 100
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        for rule in CEILING_RULES:
            if _matches_ceiling_rule(issue, rule):
                ceiling = min(ceiling, rule["limit"])
    return ceiling


# ──────────────────────────────────────────────
# 条款分代码层兜底
# ──────────────────────────────────────────────

def _is_interaction_clause(clause: Dict[str, Any]) -> bool:
    name = _norm(clause.get("clause_name"))
    return "互动" in name


def _issue_blob(issue: Dict[str, Any]) -> str:
    return " ".join(
        _norm(issue.get(key))
        for key in (
            "clause_code",
            "clause_name",
            "issue_category",
            "issue_subcategory",
            "issue_text",
        )
    )


def _is_interaction_issue(issue: Dict[str, Any]) -> bool:
    blob = _issue_blob(issue)
    return "互动" in blob or "提问" in blob or "讨论" in blob


def _interaction_cap_from_issue(issue: Dict[str, Any]):
    blob = _issue_blob(issue)
    if not _is_interaction_issue(issue):
        return None

    generic_only = _contains_any(blob, ["仅写", "仅描述", "口号", "口号化", "泛泛"])
    mentions_interaction = _contains_any(blob, ["互动", "提问", "讨论"])
    if generic_only and mentions_interaction:
        return 3
    if _contains_any(blob, ["无具体互动", "无互动设计", "没有互动", "缺少互动", "无提问", "没有提问"]):
        return 5
    if _contains_any(blob, ["无具体问题", "无具体任务", "缺少具体问题", "缺少任务设计"]):
        return 8
    if _contains_any(blob, ["互动点<2", "互动点不足", "少于2个互动", "少于两个互动"]):
        return 11
    if _contains_any(blob, ["分布不均", "集中在开头", "集中在结尾"]):
        return 13
    return None


def apply_clause_score_guards(
    clause_scores: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    对 LLM 条款分做轻量代码兜底。

    当前只强制临床小讲课“互动密度”相关上限；若修正条款分，会返回通用/分项
    分差，调用方据此同步 score_general / score_specific / score_total。
    """
    if not clause_scores:
        return {
            "clause_scores": clause_scores or [],
            "general_delta": 0,
            "specific_delta": 0,
            "flags": [],
        }

    caps = [
        cap
        for issue in issues
        if isinstance(issue, dict)
        for cap in [_interaction_cap_from_issue(issue)]
        if cap is not None
    ]
    interaction_cap = min(caps) if caps else None

    adjusted = []
    general_delta = 0.0
    specific_delta = 0.0
    flags = []

    for item in clause_scores:
        if not isinstance(item, dict):
            continue
        new_item = dict(item)
        max_score = _safe_number(new_item.get("max_score"), 100)
        actual_score = _clamp(new_item.get("actual_score"), 0, max_score)
        new_item["actual_score"] = actual_score

        if interaction_cap is not None and _is_interaction_clause(new_item) and actual_score > interaction_cap:
            new_item["actual_score"] = interaction_cap
            delta = actual_score - interaction_cap
            if _is_general_clause(new_item.get("clause_code", "")):
                general_delta += delta
            else:
                specific_delta += delta
            flags.append(f"互动密度复核：{new_item.get('clause_code', '') or '互动条款'} 已封顶至 {interaction_cap} 分")

        adjusted.append(new_item)

    return {
        "clause_scores": adjusted,
        "general_delta": general_delta,
        "specific_delta": specific_delta,
        "flags": flags,
    }


def _sum_clause_dimension(clause_scores: List[Dict[str, Any]], predicate) -> float:
    return sum(
        _safe_number(item.get("actual_score"))
        for item in clause_scores
        if isinstance(item, dict) and predicate(item.get("clause_code", ""))
    )


def _has_complete_clause_scores(clause_scores: List[Dict[str, Any]]) -> bool:
    """
    Treat clause scores as authoritative only when the report contains a full
    rubric shape. Some unit tests and guard callers pass a single clause to
    exercise a cap; those partial inputs still need the summary fallback.
    """
    general_count = sum(
        1 for item in clause_scores
        if isinstance(item, dict) and _is_general_clause(item.get("clause_code", ""))
    )
    specific_count = sum(
        1 for item in clause_scores
        if isinstance(item, dict) and _is_specific_clause(item.get("clause_code", ""))
    )
    return general_count >= 6 and specific_count >= 4


CLAUSE_SCORE_FALLBACK_FLAG = (
    "条款评分明细不完整，系统已暂用汇总分完成软处理；建议重新评审。"
)


# ──────────────────────────────────────────────
# Buffer（风险缓冲）计算规则
# ──────────────────────────────────────────────

def compute_buffer(issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    根据 issues 严重程度计算 buffer_level 和 buffer_deduction。
    """
    fatal = sum(1 for i in issues if isinstance(i, dict) and _norm(i.get("severity")) == "fatal")
    major = sum(1 for i in issues if isinstance(i, dict) and _norm(i.get("severity")) == "major")

    if fatal > 0:
        return {"buffer_level": "红色", "buffer_deduction": 10}
    if major >= 3:
        return {"buffer_level": "橙色", "buffer_deduction": 5}
    if major >= 1:
        return {"buffer_level": "黄色", "buffer_deduction": 3}
    return {"buffer_level": "无", "buffer_deduction": 0}


# ──────────────────────────────────────────────
# 高分/低分复核规则
# ──────────────────────────────────────────────

def _count_severe_issues(issues: List[Dict[str, Any]]) -> Dict[str, int]:
    fatal = sum(1 for i in issues if isinstance(i, dict) and _norm(i.get("severity")) == "fatal")
    major = sum(1 for i in issues if isinstance(i, dict) and _norm(i.get("severity")) == "major")
    return {"fatal": fatal, "major": major}


def apply_score_review_guards(adjusted_score: int, issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    高分复核直接影响分档；低分复核只做结构化证据质量提示，不自动提分。
    """
    flags = []
    severe_counts = _count_severe_issues(issues)

    if adjusted_score >= 90 and (severe_counts["fatal"] > 0 or severe_counts["major"] > 0):
        adjusted_score = 89
        flags.append("高分复核：存在 fatal/major 问题，已封顶至 89 分")

    if adjusted_score < 60:
        valid_issues = [issue for issue in issues if isinstance(issue, dict)]
        if not valid_issues:
            flags.append("低分复核：低分但未输出问题项，建议人工复核")
        elif severe_counts["fatal"] == 0 and severe_counts["major"] == 0:
            flags.append("低分复核：低分但缺少 fatal/major 问题支撑，建议人工复核")

        missing_evidence = [
            issue for issue in valid_issues
            if not _norm(issue.get("evidence_position")) or not _norm(issue.get("issue_text"))
        ]
        if missing_evidence:
            flags.append(f"低分复核：{len(missing_evidence)} 项问题缺少证据位置或问题描述，建议人工复核")

    return {"adjusted_score": adjusted_score, "flags": flags}


# ──────────────────────────────────────────────
# TCI 修正规则
# ──────────────────────────────────────────────

def _has_tci_signal(tci: Dict[str, Any]) -> bool:
    if not isinstance(tci, dict):
        return False
    if str(tci.get("consistency_level") or "").strip():
        return True
    return any(
        tci.get(key) not in (None, "") and _safe_number(tci.get(key)) > 0
        for key in ("total", "l1_homepage", "l2_objectives", "l3_process")
    )


def _resolve_tci_total(tci: Dict[str, Any]):
    if not isinstance(tci, dict):
        return None

    raw_total = tci.get("total")
    total = _safe_number(raw_total)
    if raw_total not in (None, "") and total > 0:
        return total

    level = str(tci.get("consistency_level") or "").strip()
    if not level:
        return None
    if "轻度" in level:
        return 70
    if "中度" in level:
        return 50
    if "严重" in level:
        return 30
    if "高度" in level or "基本" in level:
        return 80
    return None


def apply_tci_rules(tci: Dict[str, Any], current_ceiling: int) -> Dict[str, Any]:
    """
    应用 TCI 四级修正规则，返回 tci_deduction 和更新后的 ceiling。
    """
    if not _has_tci_signal(tci):
        return {"tci_deduction": 0, "ceiling": current_ceiling}

    tci_total = _resolve_tci_total(tci)
    if tci_total is None:
        return {"tci_deduction": 0, "ceiling": current_ceiling}

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
    clause_scores: List[Dict[str, Any]] = None,
    vetoed: bool = False,
    buffer_level: str = "无",
    buffer_deduction: float = 0,
) -> Dict[str, Any]:
    """
    代码层评分控制器 —— 统一归口总分、缓冲带、TCI 和结论。

    score_total 由 score_general + score_specific 归一化得到；只有两个分项都缺失时才
    回退使用 LLM 的 score_total。adjusted_score 不信任 LLM 预扣后的值，避免二次扣分。
    本函数职责：
      1. 检测上限锁定（从 issues 关键词）
      2. 应用 TCI 修正（deduction / ceiling）
      3. 计算 buffer（风险缓冲扣分）
      4. 合成最终 adjusted_score 与结论

    返回:
        {
            'score_general': int,    # 完整条款分优先，否则回退 LLM summary
            'score_specific': int,   # 完整条款分优先，否则回退 LLM summary
            'score_total': int,      # score_general + score_specific
            'adjusted_score': int,   # 经代码层修正后
            'buffer_level': str,
            'buffer_deduction': int,
            'vetoed': bool,
            'conclusion': str,
            'tci_deduction': int,
            'ceiling': int,
        }
    """
    tci = tci or {}
    issues = issues or []
    clause_scores = clause_scores or []

    clause_guard = apply_clause_score_guards(clause_scores, issues)
    guarded_clause_scores = clause_guard["clause_scores"]
    review_flags = list(clause_guard["flags"])

    if _has_complete_clause_scores(guarded_clause_scores):
        score_general = min(_sum_clause_dimension(guarded_clause_scores, _is_general_clause), 45)
        score_specific = min(_sum_clause_dimension(guarded_clause_scores, _is_specific_clause), 55)
        provided_total = min(score_general + score_specific, 100)
    else:
        score_general = _clamp(llm_score_general, 0, 45)
        score_specific = _clamp(llm_score_specific, 0, 55)
        provided_total = _clamp(llm_score_total, 0, 100)
        if clause_guard["flags"]:
            score_general = max(0, score_general - clause_guard["general_delta"])
            score_specific = max(0, score_specific - clause_guard["specific_delta"])
            provided_total = max(0, provided_total - clause_guard["general_delta"] - clause_guard["specific_delta"])
        review_flags.append(CLAUSE_SCORE_FALLBACK_FLAG)

    if score_general > 0 or score_specific > 0:
        score_total = min(score_general + score_specific, 100)
    else:
        score_total = provided_total

    # ── 1. 上限锁定（issues 检测）──
    ceiling = detect_ceiling_from_issues(issues)

    # ── 2. TCI 修正 ──
    tci_result = apply_tci_rules(tci, ceiling)
    ceiling = tci_result["ceiling"]
    tci_deduction = tci_result["tci_deduction"]

    # ── 3. Buffer 计算 ──
    buffer_info = compute_buffer(issues)
    buffer_level = buffer_info["buffer_level"]
    buffer_deduction = buffer_info["buffer_deduction"]

    # ── 4. 合成 adjusted_score ──
    adjusted_score = score_total - buffer_deduction - tci_deduction
    adjusted_score = min(adjusted_score, ceiling)
    adjusted_score = max(0, int(adjusted_score))

    # ── 5. 高分/低分复核 ──
    review_result = apply_score_review_guards(adjusted_score, issues)
    adjusted_score = review_result["adjusted_score"]
    review_flags.extend(review_result["flags"])

    # ── 6. 结论 ──
    if vetoed:
        conclusion = "不合格"
    else:
        conclusion = _conclusion_from_score(adjusted_score)

    return {
        "score_general": int(score_general),
        "score_specific": int(score_specific),
        "score_total": int(score_total),
        "adjusted_score": adjusted_score,
        "buffer_level": buffer_level,
        "buffer_deduction": int(buffer_deduction),
        "vetoed": bool(vetoed),
        "conclusion": conclusion,
        "tci_deduction": int(tci_deduction),
        "ceiling": int(ceiling),
        "review_flags": review_flags,
        "clause_scores": clause_guard["clause_scores"],
    }
