import json
import time
from typing import Dict

from werkzeug.exceptions import RequestEntityTooLarge

from .extractors import allowed_file, extract_text_from_docx, extract_text_from_pdf, normalize_text
from .llm_client import LLMClient
from .parser import coerce_result, count_issue_severity, extract_json_and_markdown
from .prompts import PROMPT_VERSION, build_system_prompt
from .report_markdown import sync_report_markdown
from .scoring_controller import apply_scoring_rules


def _format_bytes(size: int) -> str:
    mb = size / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.0f}MB" if mb.is_integer() else f"{mb:.1f}MB"
    kb = size / 1024
    return f"{kb:.0f}KB" if kb >= 1 else f"{size}B"


def _ensure_size_within_limit(size, max_file_bytes):
    if not max_file_bytes or not size:
        return
    if int(size) > int(max_file_bytes):
        raise RequestEntityTooLarge(f"上传文件过大，最大支持 {_format_bytes(int(max_file_bytes))}")


def _read_uploaded_bytes(uploaded, max_file_bytes):
    _ensure_size_within_limit(getattr(uploaded, "content_length", None), max_file_bytes)
    if not max_file_bytes:
        return uploaded.read()

    file_bytes = uploaded.stream.read(int(max_file_bytes) + 1)
    if len(file_bytes) > int(max_file_bytes):
        raise RequestEntityTooLarge(f"上传文件过大，最大支持 {_format_bytes(int(max_file_bytes))}")
    return file_bytes


def get_text_content(flask_request, allowed_extensions, min_len, max_len, max_file_bytes=None):
    text_content = ""
    source_mode = "text"
    filename = ""

    _ensure_size_within_limit(getattr(flask_request, "content_length", None), max_file_bytes)

    if "file" in flask_request.files and flask_request.files["file"].filename:
        uploaded = flask_request.files["file"]
        filename = uploaded.filename
        if not allowed_file(filename, allowed_extensions):
            raise ValueError("仅支持 .docx / .pdf / .txt 格式")
        ext = filename.rsplit(".", 1)[1].lower()
        file_bytes = _read_uploaded_bytes(uploaded, max_file_bytes)
        if ext == "docx":
            text_content = extract_text_from_docx(file_bytes)
        elif ext == "pdf":
            text_content = extract_text_from_pdf(file_bytes)
        else:
            text_content = file_bytes.decode("utf-8", errors="replace")
        source_mode = "file"

    pasted = flask_request.form.get("text_content", "").strip()
    if pasted:
        if text_content:
            text_content = pasted + "\n\n" + text_content
        else:
            text_content = pasted

    text_content = normalize_text(text_content, max_len)
    if len(text_content.strip()) < min_len:
        raise ValueError("教案内容过短，请确认文件是否正确上传")

    metadata = {
        "declared_type": "",
        "review_round": 1,
        "filename": filename,
        "source_mode": source_mode,
    }
    return text_content, metadata


def evaluate_text(app_config: Dict, text_content: str, metadata: Dict) -> Dict:
    user_prompt = "请对以下教案进行结构化评审，并按约定标签输出：\n\n" + text_content
    system_prompt = build_system_prompt(metadata.get("declared_type", ""))
    client = LLMClient(
        api_key=app_config["LLM_API_KEY"],
        api_base=app_config["LLM_API_BASE"],
        model_name=app_config["LLM_MODEL_NAME"],
    )

    t0 = time.time()
    raw_response = client.generate(
        system_prompt,
        user_prompt,
        timeout=app_config["LLM_TIMEOUT_SEC"],
    )
    duration = time.time() - t0

    structured, markdown = extract_json_and_markdown(raw_response)
    structured = coerce_result(structured, markdown)
    summary = structured["summary"]
    document_metadata = structured.get("document_metadata", {})
    tci = structured.get("tci", {})
    objective_matrix = structured.get("objective_matrix", {})
    severity_counts = count_issue_severity(structured["issues"])

    # ── 代码层评分控制器修正（V3.2）──
    scoring_result = apply_scoring_rules(
        llm_score_general=summary.get("score_general", 0),
        llm_score_specific=summary.get("score_specific", 0),
        llm_score_total=summary.get("score_total", 0),
        llm_adjusted_score=summary.get("adjusted_score", summary.get("score_total", 0)),
        tci=tci,
        issues=structured.get("issues", []),
        clause_scores=structured.get("clause_scores", []),
        vetoed=summary.get("vetoed", False),
        buffer_level=summary.get("buffer_level", "无"),
        buffer_deduction=summary.get("buffer_deduction", 0),
    )
    # 用代码层计算结果覆盖 LLM 原始输出
    summary["score_general"] = scoring_result["score_general"]
    summary["score_specific"] = scoring_result["score_specific"]
    summary["score_total"] = scoring_result["score_total"]
    summary["adjusted_score"] = scoring_result["adjusted_score"]
    summary["buffer_level"] = scoring_result["buffer_level"]
    summary["buffer_deduction"] = scoring_result["buffer_deduction"]
    summary["vetoed"] = scoring_result["vetoed"]
    summary["conclusion"] = scoring_result["conclusion"]
    structured["clause_scores"] = scoring_result.get("clause_scores", structured["clause_scores"])
    structured["review_flags"] = scoring_result.get("review_flags", [])
    if structured["review_flags"]:
        structured["check_log"] = structured.get("check_log", []) + structured["review_flags"]
    markdown = sync_report_markdown(markdown, summary, scoring_result)

    result = {
        "filename": metadata.get("filename", ""),
        "source_mode": metadata.get("source_mode", "text"),
        "declared_type": summary["declared_type"],
        "actual_type": summary["actual_type"],
        "department": document_metadata.get("department", "不详"),
        "teacher_name": document_metadata.get("teacher_name", "不详"),
        "course_title": document_metadata.get("course_title", "不详"),
        "review_round": metadata.get("review_round", 1),
        "prompt_version": PROMPT_VERSION,
        "model_name": app_config["LLM_MODEL_NAME"],
        "score_general": summary["score_general"],
        "score_specific": summary["score_specific"],
        "score_total": summary["score_total"],
        "adjusted_score": summary["adjusted_score"],
        "buffer_level": summary["buffer_level"],
        "buffer_deduction": summary["buffer_deduction"],
        "vetoed": summary["vetoed"],
        "conclusion": summary["conclusion"],
        "tci_total": tci.get("total", 0),
        "tci_level": tci.get("consistency_level", ""),
        "obj_matrix_total": objective_matrix.get("total_score", 0),
        "obj_completeness": (objective_matrix.get("completeness") or {}).get("score", 0),
        "obj_reasonableness": (objective_matrix.get("reasonableness") or {}).get("score", 0),
        "obj_measurability": (objective_matrix.get("measurability") or {}).get("score", 0),
        "obj_alignment": (objective_matrix.get("alignment") or {}).get("score", 0),
        "check_log": structured.get("check_log", []),
        "review_flags": structured.get("review_flags", []),
        "char_count": len(text_content),
        "duration_sec": round(duration, 1),
        "issue_count": len(structured["issues"]),
        "fatal_count": severity_counts["fatal"],
        "major_count": severity_counts["major"],
        "minor_count": severity_counts["minor"],
        "note_count": severity_counts["note"],
        "strengths": structured["strengths"],
        "suggestions": structured["suggestions"],
        "structured_json": structured,
        "issues": structured["issues"],
        "clause_scores": structured["clause_scores"],
        "raw_markdown": markdown,
        "status": "success",
    }
    return result
