import json
import time
from typing import Dict

from .extractors import allowed_file, extract_text_from_docx, extract_text_from_pdf, normalize_text
from .llm_client import LLMClient
from .parser import coerce_result, count_issue_severity, extract_json_and_markdown
from .prompts import PROMPT_VERSION, build_system_prompt


def get_text_content(flask_request, allowed_extensions, min_len, max_len):
    text_content = ""
    source_mode = "text"
    filename = ""

    if "file" in flask_request.files and flask_request.files["file"].filename:
        uploaded = flask_request.files["file"]
        filename = uploaded.filename
        if not allowed_file(filename, allowed_extensions):
            raise ValueError("仅支持 .docx / .pdf / .txt 格式")
        ext = filename.rsplit(".", 1)[1].lower()
        file_bytes = uploaded.read()
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
        "department": flask_request.form.get("department", "").strip(),
        "teacher_name": flask_request.form.get("teacher_name", "").strip(),
        "course_title": flask_request.form.get("course_title", "").strip(),
        "declared_type": flask_request.form.get("declared_type", "").strip(),
        "review_round": 1,
        "filename": filename,
        "source_mode": source_mode,
    }
    try:
        metadata["review_round"] = int(flask_request.form.get("review_round") or 1)
    except (TypeError, ValueError):
        metadata["review_round"] = 1
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
    tci = structured.get("tci", {})
    objective_matrix = structured.get("objective_matrix", {})
    severity_counts = count_issue_severity(structured["issues"])

    result = {
        "filename": metadata.get("filename", ""),
        "source_mode": metadata.get("source_mode", "text"),
        "declared_type": metadata.get("declared_type") or summary["declared_type"],
        "actual_type": summary["actual_type"],
        "department": metadata.get("department", ""),
        "teacher_name": metadata.get("teacher_name", ""),
        "course_title": metadata.get("course_title", ""),
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
