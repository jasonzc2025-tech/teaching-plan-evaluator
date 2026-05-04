import re
from typing import Any, Dict


def _display_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}".rstrip("0").rstrip(".")


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def _deduction(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0
    if number <= 0:
        return "0"
    return f"-{_display_number(number)}"


def _strip_markdown(value: str) -> str:
    return re.sub(r"[*_`]", "", value or "").strip()


def _format_table_row(cells, label: str, value: str, max_value: str = None) -> str:
    if len(cells) <= 2 or max_value is None:
        return f"| {label} | {value} |"
    return f"| {label} | {value} | {max_value} |"


def _sync_table_score_row(line: str, summary: Dict[str, Any], scoring: Dict[str, Any]) -> str:
    if set(line.replace("|", "").strip()) <= {"-"}:
        return line

    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if not cells:
        return line

    label_text = _strip_markdown(cells[0])
    score_total = _display_number(summary.get("score_total"))
    adjusted_score = _display_number(summary.get("adjusted_score"))
    conclusion = summary.get("conclusion") or "不合格"

    if label_text in {"通用维度", "通用维度 (G1-G6)", "通用维度(G1-G6)"}:
        return _format_table_row(cells, "通用维度 (G1-G6)", _display_number(summary.get("score_general")), "45")
    if label_text.startswith("分项维度"):
        return _format_table_row(cells, "分项维度", _display_number(summary.get("score_specific")), "55")
    if label_text in {"总分", "本体总分", "总分 (score_total)", "score_total"}:
        return _format_table_row(cells, "**总分 (score_total)**", f"**{score_total}**", "**100**")
    if (
        (label_text.startswith("Buffer") and "扣分" in label_text)
        or ("缓冲" in label_text and "扣分" in label_text)
    ):
        return _format_table_row(cells, "Buffer 风险扣分", _deduction(summary.get("buffer_deduction")), "—")
    if label_text.startswith("TCI 修正扣分") or label_text.startswith("TCI修正扣分"):
        return _format_table_row(cells, "TCI 修正扣分", _deduction(scoring.get("tci_deduction", 0)), "—")
    if label_text.startswith("调整后总分"):
        return _format_table_row(cells, "**调整后总分 (adjusted_score)**", f"**{adjusted_score}**", "**100**")
    if label_text in {"总分（调整后）", "总分(调整后)", "调整分"}:
        if len(cells) <= 2:
            return f"| 总分（调整后） | **{adjusted_score} / 100** |"
        return _format_table_row(cells, "总分（调整后）", f"**{adjusted_score}**", "**100**")
    if label_text in {"最终结论", "评分结论", "结论"}:
        return _format_table_row(cells, "**最终结论**", f"**{conclusion}**", "—" if len(cells) > 2 else None)
    return line


def build_score_overview(summary: Dict[str, Any], scoring: Dict[str, Any] = None) -> str:
    scoring = scoring or {}
    ceiling = int(scoring.get("ceiling", 100) or 100)
    score_total = _number(summary.get("score_total"))
    buffer_deduction = _number(summary.get("buffer_deduction"))
    tci_deduction = _number(scoring.get("tci_deduction", 0))
    deducted_score = max(0, score_total - buffer_deduction - tci_deduction)
    rows = [
        "## 二、评分总览",
        "",
        "| 维度 | 得分 | 满分 |",
        "|------|------|------|",
        f"| 通用维度 (G1-G6) | {_display_number(summary.get('score_general'))} | 45 |",
        f"| 分项维度 | {_display_number(summary.get('score_specific'))} | 55 |",
        f"| **总分 (score_total)** | **{_display_number(summary.get('score_total'))}** | **100** |",
        f"| Buffer 风险扣分 | {_deduction(summary.get('buffer_deduction'))} | — |",
        f"| TCI 修正扣分 | {_deduction(scoring.get('tci_deduction', 0))} | — |",
        f"| 扣分后分数 | {_display_number(score_total)} - {_display_number(buffer_deduction)} - {_display_number(tci_deduction)} = {_display_number(deducted_score)} | — |",
    ]
    if ceiling < 100:
        rows.append(f"| 上限锁定 | min({_display_number(deducted_score)}, {ceiling}) = {_display_number(summary.get('adjusted_score'))} | — |")
    else:
        rows.append("| 上限锁定 | 无 | — |")
    rows.extend([
        f"| **调整后总分 (adjusted_score)** | **{_display_number(summary.get('adjusted_score'))}** | **100** |",
        f"| **最终结论** | **{summary.get('conclusion') or '不合格'}** | — |",
    ])
    fallback_warning = _clause_score_fallback_warning(scoring)
    if fallback_warning:
        rows.extend([
            "",
            f'<p style="color:#c2413a;font-weight:700;">【红色提示】{fallback_warning}</p>',
        ])
    return "\n".join(rows)


def _clause_score_fallback_warning(scoring: Dict[str, Any]) -> str:
    for flag in scoring.get("review_flags", []) or []:
        text = str(flag or "").strip()
        if "条款评分明细不完整" in text:
            return text
    return ""


def _remove_score_overview_sections(markdown: str) -> str:
    score_section_pattern = re.compile(
        r"^##\s*(?:[一二三四五六七八九十]+[、.．]\s*|\d+[、.．]\s*)?评分(?:总览|概览)\s*\n.*?(?=^#{1,2}\s+|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    return score_section_pattern.sub("", markdown or "").strip()


def _insert_score_overview(markdown: str, overview: str) -> str:
    insert_pattern = re.compile(
        r"(^##\s*(?:一[、.．]\s*|1[、.．]\s*)?基本信息\s*\n.*?)(?=^##\s+|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )
    if insert_pattern.search(markdown):
        return insert_pattern.sub(r"\1" + overview + "\n\n", markdown, count=1)
    if markdown:
        return overview + "\n\n" + markdown
    return overview


def sync_report_markdown(markdown: str, summary: Dict[str, Any], scoring: Dict[str, Any] = None) -> str:
    """
    Make the human-readable report use the same authoritative scores as summary.

    The LLM may produce a Markdown table before the code layer recalculates buffer/TCI.
    Replacing the score overview avoids a final report with JSON and text disagreeing.
    """
    markdown = markdown or ""
    overview = build_score_overview(summary, scoring)
    synced = _insert_score_overview(_remove_score_overview_sections(markdown), overview)

    synced = re.sub(
        r"(?m)^(\s*[-*]\s*得分\s*[：:]\s*)\d+(?:\.\d+)?\s*$",
        rf"\g<1>{_display_number(summary.get('adjusted_score'))}",
        synced,
    )
    synced = re.sub(
        r"(?m)^(\s*[-*]\s*结论\s*[：:]\s*).*$",
        rf"\g<1>{summary.get('conclusion') or '不合格'}",
        synced,
    )
    synced = re.sub(
        r"(?m)^(\s*评分结论\s*[：:]\s*).*$",
        rf"\g<1>{summary.get('conclusion') or '不合格'}",
        synced,
    )
    synced = re.sub(
        r"(?m)^(\|\s*\*{0,2}(?:最终结论|评分结论|结论)\*{0,2}\s*\|\s*)\*{0,2}[^|\n]*?\*{0,2}(\s*\|.*)$",
        rf"\g<1>**{summary.get('conclusion') or '不合格'}**\g<2>",
        synced,
    )
    synced = re.sub(
        r"(?m)^\|.*\|$",
        lambda match: _sync_table_score_row(match.group(0), summary, scoring or {}),
        synced,
    )
    synced = re.sub(
        r"经调整后总分为\s*\d+(?:\.\d+)?\s*分",
        f"经调整后总分为{_display_number(summary.get('adjusted_score'))}分",
        synced,
    )
    synced = re.sub(
        r"调整后总分为\s*\d+(?:\.\d+)?\s*分",
        f"调整后总分为{_display_number(summary.get('adjusted_score'))}分",
        synced,
    )
    synced = re.sub(
        r"结论为\*{0,2}(优秀|良好|中等|及格|不合格|不及格)\*{0,2}",
        f"结论为**{summary.get('conclusion') or '不合格'}**",
        synced,
    )
    return synced
