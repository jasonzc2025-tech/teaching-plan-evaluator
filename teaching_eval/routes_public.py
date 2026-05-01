import json

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from .activity_guides import get_activity_guide
from .llm_client import LLMClient
from .parser import coerce_result, count_issue_severity, extract_json_and_markdown
from .precheck import run_precheck
from .prompts import PROMPT_VERSION, build_system_prompt
from .repository import save_evaluation
from .scoring_controller import apply_scoring_rules
from .services import get_text_content


public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    return render_template("index.html")


@public_bp.route("/activity_guide", methods=["GET"])
def activity_guide():
    activity_type = request.args.get("type", "").strip()
    return jsonify(get_activity_guide(activity_type))


@public_bp.route("/get_round", methods=["GET"])
def get_round():
    """根据老师名+课程名查询下一轮次。"""
    teacher = request.args.get("teacher_name", "").strip()
    course = request.args.get("course_title", "").strip()
    if not teacher or not course:
        return jsonify({"round": 1})
    try:
        import sqlite3
        conn = sqlite3.connect(current_app.config["DB_PATH"])
        row = conn.execute(
            "SELECT COUNT(*) FROM records WHERE teacher_name=? AND course_title=?",
            (teacher, course)
        ).fetchone()
        conn.close()
        next_round = (row[0] or 0) + 1
        return jsonify({"round": next_round})
    except Exception as e:
        return jsonify({"round": 1, "error": str(e)})


@public_bp.route("/precheck", methods=["POST"])
def precheck():
    try:
        text_content, metadata = get_text_content(
            request,
            current_app.config["ALLOWED_EXTENSIONS"],
            current_app.config["MIN_TEXT_LENGTH"],
            current_app.config["MAX_TEXT_LENGTH"],
        )
        return jsonify(run_precheck(text_content, metadata))
    except Exception as exc:
        return jsonify({"error": f"提交前自查失败: {exc}"}), 400


@public_bp.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": current_app.config["VERSION"],
        "app_name": current_app.config["APP_NAME"],
    })


@public_bp.route("/evaluate", methods=["POST"])
def evaluate():
    """非流式接口，保留兼容。"""
    try:
        text_content, metadata = get_text_content(
            request,
            current_app.config["ALLOWED_EXTENSIONS"],
            current_app.config["MIN_TEXT_LENGTH"],
            current_app.config["MAX_TEXT_LENGTH"],
        )
        from .services import evaluate_text
        result = evaluate_text(current_app.config, text_content, metadata)
        record_id = save_evaluation(current_app.config["DB_PATH"], result)
        return jsonify({
            "record_id": record_id,
            "result_markdown": result["raw_markdown"],
            "summary": result["structured_json"]["summary"],
            "issues": result["issues"],
            "clause_scores": result["clause_scores"],
            "strengths": result["strengths"],
            "suggestions": result["suggestions"],
            "char_count": result["char_count"],
            "duration_sec": result["duration_sec"],
        })
    except Exception as exc:
        return jsonify({"error": f"分析失败: {exc}"}), 400


@public_bp.route("/evaluate_stream", methods=["POST"])
def evaluate_stream():
    """
    真正的流式接口。
    先把 LLM token 逐个推给前端（type=token），
    等全文生成完毕再解析结构化数据，推送最终结果（done=true）。
    """
    try:
        text_content, metadata = get_text_content(
            request,
            current_app.config["ALLOWED_EXTENSIONS"],
            current_app.config["MIN_TEXT_LENGTH"],
            current_app.config["MAX_TEXT_LENGTH"],
        )
    except Exception as exc:
        def err_gen():
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        return Response(err_gen(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                        status=400)

    cfg = current_app.config

    def generate():
        import time
        client = LLMClient(
            api_key=cfg["LLM_API_KEY"],
            api_base=cfg["LLM_API_BASE"],
            model_name=cfg["LLM_MODEL_NAME"],
        )
        user_prompt = "请对以下教案进行结构化评审，并按约定标签输出：\n\n" + text_content

        full_text = ""
        t0 = time.time()

        try:
            for token in client.stream(build_system_prompt(metadata.get("declared_type", "")), user_prompt, timeout=300):
                full_text += token
                # 推送实时 token 给前端
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': f'LLM调用失败: {exc}'}, ensure_ascii=False)}\n\n"
            return

        duration = round(time.time() - t0, 1)

        # 全文生成完毕，解析结构化数据
        try:
            structured, markdown = extract_json_and_markdown(full_text)
            structured = coerce_result(structured, markdown)
            severity_counts = count_issue_severity(structured["issues"])
            summary = structured["summary"]

            # V3.1 代码层评分修正（流式接口也要执行）
            scoring_result = apply_scoring_rules(
                llm_score_general=summary.get("score_general", 0),
                llm_score_specific=summary.get("score_specific", 0),
                llm_score_total=summary.get("score_total", 0),
                llm_adjusted_score=summary.get("adjusted_score", summary.get("score_total", 0)),
                tci=structured.get("tci", {}),
                issues=structured.get("issues", []),
                vetoed=summary.get("vetoed", False),
                buffer_level=summary.get("buffer_level", "无"),
                buffer_deduction=summary.get("buffer_deduction", 0),
            )
            # 用代码层结果覆盖 LLM 原始分数
            summary["score_general"] = scoring_result["score_general"]
            summary["score_specific"] = scoring_result["score_specific"]
            summary["score_total"] = scoring_result["score_total"]
            summary["adjusted_score"] = scoring_result["adjusted_score"]
            summary["buffer_level"] = scoring_result["buffer_level"]
            summary["buffer_deduction"] = scoring_result["buffer_deduction"]
            summary["vetoed"] = scoring_result["vetoed"]
            summary["conclusion"] = scoring_result["conclusion"]


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
                "model_name": cfg["LLM_MODEL_NAME"],
                "score_general": summary["score_general"],
                "score_specific": summary["score_specific"],
                "score_total": summary["score_total"],
                "adjusted_score": summary.get("adjusted_score", summary["score_total"]),
                "buffer_level": summary.get("buffer_level", "无"),
                "buffer_deduction": summary.get("buffer_deduction", 0),
                "vetoed": summary["vetoed"],
                "conclusion": summary["conclusion"],
                "tci_total": summary.get("tci_total", 0),
                "tci_level": summary.get("tci_level", ""),
                "obj_matrix_total": summary.get("obj_matrix_total", 0),
                "obj_completeness": summary.get("obj_completeness", 0),
                "obj_reasonableness": summary.get("obj_reasonableness", 0),
                "obj_measurability": summary.get("obj_measurability", 0),
                "obj_alignment": summary.get("obj_alignment", 0),
                "check_log": structured.get("check_log", []),
                "char_count": len(text_content),
                "duration_sec": duration,
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

            record_id = save_evaluation(cfg["DB_PATH"], result)

            final = {
                "done": True,
                "record_id": record_id,
                "result_markdown": markdown,
                "summary": summary,
                "issues": structured["issues"],
                "clause_scores": structured["clause_scores"],
                "strengths": structured["strengths"],
                "suggestions": structured["suggestions"],
                "duration_sec": duration,
            }
            yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'error': f'结果解析失败: {exc}'}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
