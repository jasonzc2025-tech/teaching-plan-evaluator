import json
from datetime import datetime
from typing import Dict, List

from .db import get_connection


def save_evaluation(db_path: str, payload: Dict) -> int:
    conn = get_connection(db_path)
    cur = conn.cursor()

    record_sql = """
    INSERT INTO records (
        created_at, filename, source_mode, declared_type, actual_type, department,
        teacher_name, course_title, review_round, prompt_version, model_name,
        score_general, score_specific, score_total, adjusted_score, buffer_level, buffer_deduction,
        vetoed, conclusion, tci_total, tci_level, obj_matrix_total, obj_completeness,
        obj_reasonableness, obj_measurability, obj_alignment, check_log_json, char_count,
        duration_sec, issue_count, fatal_count, major_count, minor_count, note_count,
        strengths_json, suggestions_json, structured_json, raw_markdown, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cur.execute(
        record_sql,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            payload.get("filename", ""),
            payload.get("source_mode", "text"),
            payload.get("declared_type", ""),
            payload.get("actual_type", ""),
            payload.get("department", ""),
            payload.get("teacher_name", ""),
            payload.get("course_title", ""),
            payload.get("review_round", 1),
            payload.get("prompt_version", ""),
            payload.get("model_name", ""),
            payload.get("score_general", 0),
            payload.get("score_specific", 0),
            payload.get("score_total", 0),
            payload.get("adjusted_score", payload.get("score_total", 0)),
            payload.get("buffer_level", "无"),
            payload.get("buffer_deduction", 0),
            1 if payload.get("vetoed") else 0,
            payload.get("conclusion", ""),
            payload.get("tci_total", 0),
            payload.get("tci_level", ""),
            payload.get("obj_matrix_total", 0),
            payload.get("obj_completeness", 0),
            payload.get("obj_reasonableness", 0),
            payload.get("obj_measurability", 0),
            payload.get("obj_alignment", 0),
            json.dumps(payload.get("check_log", []), ensure_ascii=False),
            payload.get("char_count", 0),
            payload.get("duration_sec", 0),
            payload.get("issue_count", 0),
            payload.get("fatal_count", 0),
            payload.get("major_count", 0),
            payload.get("minor_count", 0),
            payload.get("note_count", 0),
            json.dumps(payload.get("strengths", []), ensure_ascii=False),
            json.dumps(payload.get("suggestions", []), ensure_ascii=False),
            json.dumps(payload.get("structured_json", {}), ensure_ascii=False),
            payload.get("raw_markdown", ""),
            payload.get("status", "success"),
        ),
    )
    record_id = cur.lastrowid

    issue_sql = """
    INSERT INTO record_issues (
        record_id, clause_code, clause_name, issue_category, issue_subcategory, severity,
        is_veto_related, evidence_position, issue_text, suggestion_text, score_loss
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    for item in payload.get("issues", []):
        cur.execute(
            issue_sql,
            (
                record_id,
                item.get("clause_code", ""),
                item.get("clause_name", ""),
                item.get("issue_category", ""),
                item.get("issue_subcategory", ""),
                item.get("severity", ""),
                1 if item.get("is_veto_related") else 0,
                item.get("evidence_position", ""),
                item.get("issue_text", ""),
                item.get("suggestion_text", ""),
                item.get("score_loss", 0),
            ),
        )

    clause_sql = """
    INSERT INTO clause_scores (
        record_id, clause_code, clause_name, max_score, actual_score, evidence_position, judgment_text
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    for item in payload.get("clause_scores", []):
        cur.execute(
            clause_sql,
            (
                record_id,
                item.get("clause_code", ""),
                item.get("clause_name", ""),
                item.get("max_score", 0),
                item.get("actual_score", 0),
                item.get("evidence_position", ""),
                item.get("judgment_text", ""),
            ),
        )

    conn.commit()
    conn.close()
    return record_id


def fetch_dashboard_data(db_path: str) -> Dict:
    conn = get_connection(db_path)

    total = conn.execute("SELECT COUNT(*) AS c FROM records").fetchone()["c"]
    today = conn.execute(
        "SELECT COUNT(*) AS c FROM records WHERE created_at LIKE ?",
        (datetime.now().strftime("%Y-%m-%d") + "%",),
    ).fetchone()["c"]
    avg_score = conn.execute(
        "SELECT AVG(score_total) AS v FROM records WHERE score_total IS NOT NULL"
    ).fetchone()["v"]
    vetoed = conn.execute("SELECT COUNT(*) AS c FROM records WHERE vetoed=1").fetchone()["c"]
    avg_duration = conn.execute(
        "SELECT AVG(duration_sec) AS v FROM records WHERE duration_sec IS NOT NULL"
    ).fetchone()["v"]
    avg_issue_count = conn.execute(
        "SELECT AVG(issue_count) AS v FROM records WHERE issue_count IS NOT NULL"
    ).fetchone()["v"]

    by_type = [dict(row) for row in conn.execute(
        """
        SELECT COALESCE(actual_type, declared_type, '未知') AS doc_type,
               COUNT(*) AS cnt,
               AVG(score_total) AS avg_score,
               AVG(major_count) AS avg_major
        FROM records
        GROUP BY COALESCE(actual_type, declared_type, '未知')
        ORDER BY cnt DESC
        """
    ).fetchall()]

    severity_counts = [dict(row) for row in conn.execute(
        """
        SELECT severity, COUNT(*) AS cnt
        FROM record_issues
        GROUP BY severity
        ORDER BY cnt DESC
        """
    ).fetchall()]

    top_issue_categories = [dict(row) for row in conn.execute(
        """
        SELECT issue_category, COUNT(*) AS cnt
        FROM record_issues
        GROUP BY issue_category
        ORDER BY cnt DESC
        LIMIT 10
        """
    ).fetchall()]

    top_issue_subcategories = [dict(row) for row in conn.execute(
        """
        SELECT issue_subcategory, COUNT(*) AS cnt
        FROM record_issues
        WHERE issue_subcategory IS NOT NULL AND issue_subcategory <> ''
        GROUP BY issue_subcategory
        ORDER BY cnt DESC
        LIMIT 10
        """
    ).fetchall()]

    daily = [dict(row) for row in conn.execute(
        """
        SELECT substr(created_at, 1, 10) AS day,
               COUNT(*) AS cnt,
               AVG(score_total) AS avg_score
        FROM records
        WHERE created_at >= date('now', '-14 days')
        GROUP BY day
        ORDER BY day
        """
    ).fetchall()]

    # 按老师统计上传次数、平均分
    by_teacher = [dict(row) for row in conn.execute(
        """
        SELECT teacher_name, COUNT(*) AS cnt, AVG(score_total) AS avg_score
        FROM records
        WHERE teacher_name IS NOT NULL AND teacher_name <> ''
        GROUP BY teacher_name
        ORDER BY cnt DESC
        LIMIT 20
        """
    ).fetchall()]

    # 按科室统计
    by_dept = [dict(row) for row in conn.execute(
        """
        SELECT department, COUNT(*) AS cnt, AVG(score_total) AS avg_score
        FROM records
        WHERE department IS NOT NULL AND department <> ''
        GROUP BY department
        ORDER BY cnt DESC
        LIMIT 20
        """
    ).fetchall()]

    # 按文件名/课程统计评审轮次（同一课程名提交次数 = 评审轮次）
    round_stats = [dict(row) for row in conn.execute(
        """
        SELECT
            COALESCE(course_title, filename, '未知') AS course,
            teacher_name,
            department,
            COUNT(*) AS total_rounds,
            MAX(review_round) AS max_round,
            MIN(score_total) AS first_score,
            MAX(score_total) AS best_score,
            MAX(created_at) AS last_reviewed
        FROM records
        WHERE course_title IS NOT NULL AND course_title <> ''
        GROUP BY COALESCE(course_title, filename, '未知')
        HAVING COUNT(*) > 1
        ORDER BY total_rounds DESC, last_reviewed DESC
        LIMIT 20
        """
    ).fetchall()]

    recent_records = [dict(row) for row in conn.execute(
        """
        SELECT id, created_at, filename, department, teacher_name, course_title,
               declared_type, actual_type, score_total, conclusion,
               vetoed, duration_sec, issue_count, major_count, review_round
        FROM records
        ORDER BY id DESC
        LIMIT 50
        """
    ).fetchall()]

    conn.close()
    return {
        "total": total,
        "today": today,
        "avg_score": round(avg_score or 0, 1),
        "vetoed": vetoed,
        "avg_duration": round(avg_duration or 0, 1),
        "avg_issue_count": round(avg_issue_count or 0, 1),
        "by_type": by_type,
        "severity_counts": severity_counts,
        "top_issue_categories": top_issue_categories,
        "top_issue_subcategories": top_issue_subcategories,
        "daily": daily,
        "by_teacher": by_teacher,
        "by_dept": by_dept,
        "round_stats": round_stats,
        "recent_records": recent_records,
    }


def fetch_record_detail(db_path: str, record_id: int) -> Dict:
    conn = get_connection(db_path)
    record = conn.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    if not record:
        conn.close()
        return {}

    issues = [dict(row) for row in conn.execute(
        """
        SELECT * FROM record_issues
        WHERE record_id = ?
        ORDER BY
            CASE severity
                WHEN 'fatal' THEN 1
                WHEN 'major' THEN 2
                WHEN 'minor' THEN 3
                ELSE 4
            END,
            id
        """,
        (record_id,),
    ).fetchall()]

    clause_scores = [dict(row) for row in conn.execute(
        "SELECT * FROM clause_scores WHERE record_id = ? ORDER BY id",
        (record_id,),
    ).fetchall()]

    conn.close()
    return {
        "record": dict(record),
        "issues": issues,
        "clause_scores": clause_scores,
    }


def export_table_rows(db_path: str, table_name: str) -> List[Dict]:
    allowed_tables = {"records", "record_issues", "clause_scores"}
    if table_name not in allowed_tables:
        raise ValueError("不允许导出该表")
    conn = get_connection(db_path)
    rows = [dict(row) for row in conn.execute(
        f"SELECT * FROM {table_name} ORDER BY id DESC"
    ).fetchall()]
    conn.close()
    return rows


def fetch_compare_data(db_path: str) -> Dict:
    """按课程/文件名分组，返回多轮评审对比数据。"""
    conn = get_connection(db_path)
    rows = [dict(row) for row in conn.execute(
        """
        SELECT
            COALESCE(course_title, filename, '未知') AS course,
            teacher_name, department,
            COUNT(*) AS total_rounds,
            MIN(score_total) AS first_score,
            MAX(score_total) AS best_score,
            MAX(created_at) AS last_reviewed
        FROM records
        WHERE course_title IS NOT NULL AND course_title <> ''
        GROUP BY COALESCE(course_title, filename, '未知')
        HAVING COUNT(*) > 1
        ORDER BY total_rounds DESC, last_reviewed DESC
        LIMIT 30
        """
    ).fetchall()]
    conn.close()
    return {"compare": rows}


def fetch_teacher_stats(db_path: str) -> List[Dict]:
    """按带教老师统计提交次数和平均分。"""
    conn = get_connection(db_path)
    rows = [dict(row) for row in conn.execute(
        """
        SELECT teacher_name, COUNT(*) AS cnt, AVG(score_total) AS avg_score
        FROM records
        WHERE teacher_name IS NOT NULL AND teacher_name <> ''
        GROUP BY teacher_name
        ORDER BY cnt DESC
        LIMIT 30
        """
    ).fetchall()]
    conn.close()
    return rows


def fetch_department_stats(db_path: str) -> List[Dict]:
    """按科室统计提交次数和平均分。"""
    conn = get_connection(db_path)
    rows = [dict(row) for row in conn.execute(
        """
        SELECT department, COUNT(*) AS cnt, AVG(score_total) AS avg_score
        FROM records
        WHERE department IS NOT NULL AND department <> ''
        GROUP BY department
        ORDER BY cnt DESC
        LIMIT 30
        """
    ).fetchall()]
    conn.close()
    return rows
