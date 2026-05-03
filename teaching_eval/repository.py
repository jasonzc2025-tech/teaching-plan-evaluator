import json
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from .db import get_connection

UNKNOWN_VALUE = "不详"


def get_next_review_round(db_path: str, teacher_name: str, course_title: str) -> int:
    teacher = (teacher_name or "").strip()
    course = (course_title or "").strip()
    if not teacher or not course or teacher == UNKNOWN_VALUE or course == UNKNOWN_VALUE:
        return 1

    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM records WHERE teacher_name=? AND course_title=?",
            (teacher, course),
        ).fetchone()
        return (row["c"] or 0) + 1
    finally:
        conn.close()


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

    veto_reasons = [dict(row) for row in conn.execute(
        """
        SELECT
            COALESCE(NULLIF(issue_category, ''), '未分类') AS issue_category,
            COALESCE(NULLIF(issue_subcategory, ''), '') AS issue_subcategory,
            COALESCE(NULLIF(clause_name, ''), NULLIF(clause_code, ''), '未关联条款') AS clause_name,
            COUNT(*) AS cnt
        FROM record_issues
        WHERE is_veto_related=1 OR severity='fatal'
        GROUP BY
            COALESCE(NULLIF(issue_category, ''), '未分类'),
            COALESCE(NULLIF(issue_subcategory, ''), ''),
            COALESCE(NULLIF(clause_name, ''), NULLIF(clause_code, ''), '未关联条款')
        ORDER BY cnt DESC
        LIMIT 10
        """
    ).fetchall()]

    low_clause_scores = [dict(row) for row in conn.execute(
        """
        SELECT
            COALESCE(NULLIF(clause_name, ''), NULLIF(clause_code, ''), '未知条款') AS clause_name,
            COUNT(*) AS samples,
            ROUND(AVG(max_score), 1) AS avg_max,
            ROUND(AVG(actual_score), 1) AS avg_actual,
            ROUND(AVG(max_score - actual_score), 1) AS avg_loss,
            ROUND(100.0 * AVG(actual_score) / NULLIF(AVG(max_score), 0), 1) AS score_rate
        FROM clause_scores
        WHERE max_score IS NOT NULL AND max_score > 0
        GROUP BY COALESCE(NULLIF(clause_name, ''), NULLIF(clause_code, ''), '未知条款')
        ORDER BY score_rate ASC, avg_loss DESC, samples DESC
        LIMIT 10
        """
    ).fetchall()]

    type_issue_rows = [dict(row) for row in conn.execute(
        """
        SELECT
            COALESCE(NULLIF(r.actual_type, ''), NULLIF(r.declared_type, ''), '未知') AS doc_type,
            COALESCE(NULLIF(i.issue_category, ''), '未分类') AS issue_category,
            COUNT(*) AS cnt,
            SUM(CASE WHEN i.severity IN ('fatal', 'major') THEN 1 ELSE 0 END) AS severe_cnt
        FROM record_issues i
        JOIN records r ON r.id = i.record_id
        GROUP BY
            COALESCE(NULLIF(r.actual_type, ''), NULLIF(r.declared_type, ''), '未知'),
            COALESCE(NULLIF(i.issue_category, ''), '未分类')
        ORDER BY doc_type ASC, cnt DESC
        """
    ).fetchall()]

    type_map = {}
    for row in type_issue_rows:
        item = type_map.setdefault(row["doc_type"], {
            "doc_type": row["doc_type"],
            "total_issues": 0,
            "severe_issues": 0,
            "top_categories": [],
        })
        item["total_issues"] += row["cnt"] or 0
        item["severe_issues"] += row["severe_cnt"] or 0
        if len(item["top_categories"]) < 3:
            item["top_categories"].append({
                "name": row["issue_category"],
                "cnt": row["cnt"],
                "severe_cnt": row["severe_cnt"] or 0,
            })
    type_weaknesses = sorted(type_map.values(), key=lambda x: x["total_issues"], reverse=True)

    dept_issue_rows = [dict(row) for row in conn.execute(
        """
        SELECT
            COALESCE(NULLIF(r.department, ''), '未标注科室') AS department,
            COALESCE(NULLIF(i.issue_category, ''), '未分类') AS issue_category,
            COUNT(*) AS cnt,
            SUM(CASE WHEN i.severity IN ('fatal', 'major') THEN 1 ELSE 0 END) AS severe_cnt
        FROM record_issues i
        JOIN records r ON r.id = i.record_id
        GROUP BY
            COALESCE(NULLIF(r.department, ''), '未标注科室'),
            COALESCE(NULLIF(i.issue_category, ''), '未分类')
        ORDER BY department ASC, cnt DESC
        """
    ).fetchall()]

    dept_map = {}
    for row in dept_issue_rows:
        item = dept_map.setdefault(row["department"], {
            "department": row["department"],
            "total_issues": 0,
            "severe_issues": 0,
            "top_categories": [],
        })
        item["total_issues"] += row["cnt"] or 0
        item["severe_issues"] += row["severe_cnt"] or 0
        if len(item["top_categories"]) < 3:
            item["top_categories"].append({
                "name": row["issue_category"],
                "cnt": row["cnt"],
                "severe_cnt": row["severe_cnt"] or 0,
            })
    department_weaknesses = sorted(
        dept_map.values(),
        key=lambda x: (x["severe_issues"], x["total_issues"]),
        reverse=True,
    )[:12]

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

    round_records = [dict(row) for row in conn.execute(
        """
        SELECT id, created_at, filename, department, teacher_name, course_title,
               score_total, major_count, fatal_count, review_round
        FROM records
        WHERE COALESCE(course_title, filename, '') <> ''
        ORDER BY COALESCE(teacher_name, ''), COALESCE(course_title, filename, ''), id ASC
        """
    ).fetchall()]

    grouped_rounds = defaultdict(list)
    for row in round_records:
        key = (
            row.get("teacher_name") or "未标注老师",
            row.get("course_title") or row.get("filename") or "未知课程",
        )
        grouped_rounds[key].append(row)

    improvement_rows = []
    for (teacher, course), rows in grouped_rounds.items():
        if len(rows) < 2:
            continue
        first = rows[0]
        latest = rows[-1]
        first_score = first.get("score_total") or 0
        latest_score = latest.get("score_total") or 0
        first_major = first.get("major_count") or 0
        latest_major = latest.get("major_count") or 0
        first_fatal = first.get("fatal_count") or 0
        latest_fatal = latest.get("fatal_count") or 0
        improvement_rows.append({
            "teacher_name": teacher,
            "course": course,
            "department": latest.get("department") or first.get("department") or "",
            "total_rounds": len(rows),
            "first_score": first_score,
            "latest_score": latest_score,
            "score_delta": round(latest_score - first_score, 1),
            "major_delta": latest_major - first_major,
            "fatal_delta": latest_fatal - first_fatal,
            "last_reviewed": latest.get("created_at") or "",
        })
    improvement_rows.sort(key=lambda x: x["last_reviewed"], reverse=True)
    improvement_summary = improvement_rows[:20]

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
        "veto_reasons": veto_reasons,
        "low_clause_scores": low_clause_scores,
        "type_weaknesses": type_weaknesses,
        "department_weaknesses": department_weaknesses,
        "daily": daily,
        "by_teacher": by_teacher,
        "by_dept": by_dept,
        "round_stats": round_stats,
        "improvement_summary": improvement_summary,
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



def fetch_teacher_stats(db_path, teacher_name):
    conn = get_connection(db_path)
    row = conn.execute("SELECT COUNT(*) AS record_count, ROUND(AVG(score_total),1) AS avg_score, ROUND(AVG(major_count),1) AS avg_major, ROUND(AVG(fatal_count),1) AS avg_fatal, ROUND(AVG(buffer_deduction),1) AS avg_buffer_deduction FROM records WHERE teacher_name=?", (teacher_name,)).fetchone()
    if not row or row["record_count"] == 0:
        conn.close()
        return {}
    summary = {k: (row[k] if row[k] is not None else 0) for k in row.keys()}
    recent = [dict(r) for r in conn.execute("SELECT id, created_at, declared_type, actual_type, score_total, conclusion, major_count FROM records WHERE teacher_name=? ORDER BY id DESC LIMIT 30", (teacher_name,)).fetchall()]
    cats = [dict(r) for r in conn.execute("SELECT i.issue_category, COUNT(*) AS cnt FROM record_issues i JOIN records r ON r.id=i.record_id WHERE r.teacher_name=? GROUP BY i.issue_category ORDER BY cnt DESC LIMIT 10", (teacher_name,)).fetchall()]
    trend = [dict(r) for r in conn.execute("SELECT substr(created_at,1,10) AS day, AVG(score_total) AS avg_score FROM records WHERE teacher_name=? GROUP BY substr(created_at,1,10) ORDER BY day ASC", (teacher_name,)).fetchall()]
    conn.close()
    return {"teacher_name": teacher_name, "summary": summary, "recent_records": recent, "top_issue_categories": cats, "trend": trend}


def fetch_department_stats(db_path):
    conn = get_connection(db_path)
    overview = [dict(r) for r in conn.execute("SELECT department, COUNT(*) AS cnt, ROUND(AVG(score_total),1) AS avg_score, ROUND(AVG(major_count),1) AS avg_major, ROUND(AVG(fatal_count),1) AS avg_fatal, ROUND(100.0*SUM(CASE WHEN buffer_deduction>0 THEN 1 ELSE 0 END)/COUNT(*),1) AS buffer_rate FROM records WHERE department IS NOT NULL AND department<>'' GROUP BY department ORDER BY cnt DESC").fetchall()]
    issues = [dict(r) for r in conn.execute("SELECT issue_category, COUNT(*) AS cnt FROM record_issues WHERE issue_category IS NOT NULL AND issue_category<>'' GROUP BY issue_category ORDER BY cnt DESC LIMIT 10").fetchall()]
    types = [dict(r) for r in conn.execute("SELECT COALESCE(actual_type, declared_type, '未知') AS doc_type, COUNT(*) AS cnt FROM records GROUP BY COALESCE(actual_type, declared_type, '未知') ORDER BY cnt DESC").fetchall()]
    conn.close()
    return {"department_overview": overview, "issue_distribution": issues, "type_distribution": types}


def fetch_compare_data(db_path, record_id):
    conn = get_connection(db_path)
    base = conn.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone()
    if not base:
        conn.close()
        return {}
    base_record = dict(base)

    # 找同一课程或同一文件名的所有轮次
    course_key = base_record.get("course_title") or base_record.get("filename") or ""
    if not course_key:
        rounds = [base_record]
    else:
        rounds = [dict(r) for r in conn.execute(
            "SELECT * FROM records WHERE COALESCE(course_title, filename, '') = ? ORDER BY id ASC",
            (course_key,)
        ).fetchall()]

    # 找上一轮（用于对比新增/解决的问题）
    prev_record = None
    for r in rounds:
        if r["id"] == record_id:
            break
        prev_record = r

    new_issues = []
    removed_issues = []

    if prev_record:
        cur_issues = [dict(r) for r in conn.execute(
            "SELECT issue_category, issue_subcategory, issue_text FROM record_issues WHERE record_id=?",
            (record_id,)
        ).fetchall()]
        prev_issues = [dict(r) for r in conn.execute(
            "SELECT issue_category, issue_subcategory, issue_text FROM record_issues WHERE record_id=?",
            (prev_record["id"],)
        ).fetchall()]

        def key(i):
            return (i.get("issue_category", ""), i.get("issue_subcategory", ""), (i.get("issue_text", "") or "")[:40])

        prev_keys = {key(i) for i in prev_issues}
        cur_keys = {key(i) for i in cur_issues}

        new_issues = [i for i in cur_issues if key(i) not in prev_keys]
        removed_issues = [i for i in prev_issues if key(i) not in cur_keys]

    conn.close()
    return {
        "base_record": base_record,
        "rounds": rounds,
        "new_issues": new_issues,
        "removed_issues": removed_issues,
    }
