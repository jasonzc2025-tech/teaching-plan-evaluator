import json
import re
from typing import Any, Dict, Tuple


JSON_PATTERN = re.compile(
    r"<STRUCTURED_JSON>\s*(\{.*?\})\s*</STRUCTURED_JSON>",
    flags=re.DOTALL,
)
MARKDOWN_PATTERN = re.compile(
    r"<REPORT_MARKDOWN>\s*(.*?)\s*</REPORT_MARKDOWN>",
    flags=re.DOTALL,
)
ALLOWED_CONCLUSIONS = {"优秀", "良好", "中等", "及格", "不及格"}


def _safe_number(value: Any, default: float = 0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_json_and_markdown(response_text: str) -> Tuple[Dict[str, Any], str]:
    structured: Dict[str, Any] = {}
    markdown = response_text.strip()

    json_match = JSON_PATTERN.search(response_text)
    if json_match:
        candidate = json_match.group(1).strip()
        try:
            structured = json.loads(candidate)
        except json.JSONDecodeError:
            structured = {}

    markdown_match = MARKDOWN_PATTERN.search(response_text)
    if markdown_match:
        markdown = markdown_match.group(1).strip()

    return structured, markdown


def build_fallback_summary(markdown_text: str) -> Dict[str, Any]:
    score_general = _search_number(markdown_text, r"通用维度得分[^:：]*[:：]\s*(\d+(?:\.\d+)?)")
    score_specific = _search_number(markdown_text, r"分项维度得分[^:：]*[:：]\s*(\d+(?:\.\d+)?)")
    score_total = _search_number(markdown_text, r"总分[^:：]*[:：]\s*(\d+(?:\.\d+)?)")
    declared_type = _search_text(markdown_text, r"教案类型[:：]\s*([^\n（(]+)")
    conclusion = _search_text(markdown_text, r"评分结论[:：]\s*([^\n]+)")
    vetoed = False
    adjusted_score = _safe_number(score_total)
    buffer_deduction = 0
    buffer_level = "无"
    return {
        "summary": {
            "declared_type": declared_type or "未知",
            "actual_type": declared_type or "未知",
            "score_general": _safe_number(score_general),
            "score_specific": _safe_number(score_specific),
            "score_total": _safe_number(score_total),
            "adjusted_score": adjusted_score,
            "buffer_level": buffer_level,
            "buffer_deduction": buffer_deduction,
            "vetoed": vetoed,
            "conclusion": conclusion or _conclusion_from_score(adjusted_score),
        },
        "clause_scores": [],
        "issues": [],
        "strengths": [],
        "suggestions": [],
    }


def _search_number(text: str, pattern: str):
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _search_text(text: str, pattern: str):
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def _conclusion_from_score(score: float) -> str:
    if score >= 90:
        return "优秀"
    if score >= 80:
        return "良好"
    if score >= 70:
        return "中等"
    if score >= 60:
        return "及格"
    return "不及格"


def _normalize_conclusion(value: str, adjusted_score: float) -> str:
    if value in ALLOWED_CONCLUSIONS:
        return value
    mapping = {
        "合格": "及格",
        "基本合格": "及格",
        "不合格": "不及格",
        "否决": "不及格",
    }
    if value in mapping:
        return mapping[value]
    return _conclusion_from_score(adjusted_score)


def coerce_result(structured: Dict[str, Any], markdown_text: str) -> Dict[str, Any]:
    if not structured or "summary" not in structured:
        structured = build_fallback_summary(markdown_text)

    summary = structured.setdefault("summary", {})
    summary["score_general"] = min(_safe_number(summary.get("score_general")), 45)
    summary["score_specific"] = min(_safe_number(summary.get("score_specific")), 55)
    summary["score_total"] = min(_safe_number(summary.get("score_total")), 100)
    summary["buffer_deduction"] = _safe_number(summary.get("buffer_deduction"))
    summary["adjusted_score"] = _safe_number(summary.get("adjusted_score"), summary["score_total"])
    if summary["adjusted_score"] <= 0 and summary["score_total"] > 0:
        summary["adjusted_score"] = max(0, summary["score_total"] - summary["buffer_deduction"])
    summary["buffer_level"] = str(summary.get("buffer_level") or "无")
    summary["vetoed"] = False
    summary["declared_type"] = summary.get("declared_type") or "未知"
    summary["actual_type"] = summary.get("actual_type") or summary["declared_type"]
    summary["conclusion"] = _normalize_conclusion(str(summary.get("conclusion") or ""), summary["adjusted_score"])

    clause_scores = structured.get("clause_scores") or []
    issues = structured.get("issues") or []
    strengths = structured.get("strengths") or []
    suggestions = structured.get("suggestions") or []
    tci = structured.get("tci") or {}
    objective_matrix = structured.get("objective_matrix") or {}
    check_log = structured.get("check_log") or []

    structured["clause_scores"] = [
        {
            "clause_code": item.get("clause_code", ""),
            "clause_name": item.get("clause_name", ""),
            "max_score": _safe_number(item.get("max_score")),
            "actual_score": _safe_number(item.get("actual_score")),
            "evidence_position": item.get("evidence_position", ""),
            "judgment_text": item.get("judgment_text", ""),
        }
        for item in clause_scores
        if isinstance(item, dict)
    ]

    structured["issues"] = [
        {
            "clause_code": item.get("clause_code", ""),
            "clause_name": item.get("clause_name", ""),
            "issue_category": item.get("issue_category", "未分类"),
            "issue_subcategory": item.get("issue_subcategory", ""),
            "severity": item.get("severity", "minor"),
            "is_veto_related": bool(item.get("is_veto_related")),
            "evidence_position": item.get("evidence_position", ""),
            "issue_text": item.get("issue_text", ""),
            "suggestion_text": item.get("suggestion_text", ""),
            "score_loss": _safe_number(item.get("score_loss")),
        }
        for item in issues
        if isinstance(item, dict)
    ]

    structured["strengths"] = [str(x) for x in strengths if str(x).strip()]
    structured["suggestions"] = [str(x) for x in suggestions if str(x).strip()]
    structured["tci"] = {
        "total": _safe_number(tci.get("total")),
        "l1_homepage": _safe_number(tci.get("l1_homepage")),
        "l2_objectives": _safe_number(tci.get("l2_objectives")),
        "l3_process": _safe_number(tci.get("l3_process")),
        "consistency_level": str(tci.get("consistency_level") or ""),
    }
    structured["objective_matrix"] = {
        "total_score": _safe_number(objective_matrix.get("total_score")),
        "completeness": objective_matrix.get("completeness") if isinstance(objective_matrix.get("completeness"), dict) else {},
        "reasonableness": objective_matrix.get("reasonableness") if isinstance(objective_matrix.get("reasonableness"), dict) else {},
        "measurability": objective_matrix.get("measurability") if isinstance(objective_matrix.get("measurability"), dict) else {},
        "alignment": objective_matrix.get("alignment") if isinstance(objective_matrix.get("alignment"), dict) else {},
        "improvement_suggestions": [
            str(x) for x in (objective_matrix.get("improvement_suggestions") or []) if str(x).strip()
        ],
    }
    structured["check_log"] = [str(x) for x in check_log if str(x).strip()]
    return structured


def count_issue_severity(issues):
    result = {"fatal": 0, "major": 0, "minor": 0, "note": 0}
    for item in issues:
        severity = item.get("severity", "minor")
        if severity not in result:
            severity = "minor"
        result[severity] += 1
    return result
