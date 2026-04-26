import csv
import io
import time

from flask import Blueprint, Response, current_app, redirect, render_template, request, session, url_for

from .repository import (
    export_table_rows,
    fetch_dashboard_data,
    fetch_record_detail,
    fetch_compare_data,
    fetch_teacher_stats,
    fetch_department_stats,
)


admin_bp = Blueprint("admin", __name__)
MAX_LOGIN_FAILS = 5
LOGIN_LOCK_SECONDS = 300


def _ensure_login():
    if not session.get("admin"):
        return redirect(url_for("admin.login"))
    return None


def _sanitize_csv_row(row):
    sanitized = {}
    for key, value in row.items():
        if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
            sanitized[key] = "'" + value
        else:
            sanitized[key] = value
    return sanitized


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def login():
    error = ""
    now = int(time.time())
    lock_until = int(session.get("admin_lock_until", 0))
    if request.method == "POST" and lock_until > now:
        remain = lock_until - now
        error = f"登录失败次数过多，请 {remain} 秒后再试"
        return render_template("login.html", error=error), 429

    if request.method == "POST":
        if request.form.get("password", "") == current_app.config["ADMIN_PASSWORD"]:
            session["admin"] = True
            session.pop("admin_fail_count", None)
            session.pop("admin_lock_until", None)
            return redirect(url_for("admin.dashboard"))
        fail_count = int(session.get("admin_fail_count", 0)) + 1
        session["admin_fail_count"] = fail_count
        if fail_count >= MAX_LOGIN_FAILS:
            session["admin_lock_until"] = now + LOGIN_LOCK_SECONDS
            session["admin_fail_count"] = 0
            error = f"登录失败次数过多，请 {LOGIN_LOCK_SECONDS} 秒后再试"
            return render_template("login.html", error=error), 429
        error = "密码错误"
    return render_template("login.html", error=error)


@admin_bp.route("/admin/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("admin.login"))


@admin_bp.route("/admin")
def dashboard():
    redirect_resp = _ensure_login()
    if redirect_resp:
        return redirect_resp
    data = fetch_dashboard_data(current_app.config["DB_PATH"])
    return render_template("admin_dashboard.html", **data)


@admin_bp.route("/admin/record/<int:record_id>")
def record_detail(record_id: int):
    redirect_resp = _ensure_login()
    if redirect_resp:
        return redirect_resp
    data = fetch_record_detail(current_app.config["DB_PATH"], record_id)
    if not data:
        return "记录不存在", 404
    return render_template("record_detail.html", **data)


@admin_bp.route("/admin/compare/<int:record_id>")
def compare_review_rounds(record_id: int):
    redirect_resp = _ensure_login()
    if redirect_resp:
        return redirect_resp
    data = fetch_compare_data(current_app.config["DB_PATH"], record_id)
    if not data:
        return "记录不存在或无法对比", 404
    return render_template("compare_review_rounds.html", **data)


@admin_bp.route("/admin/teacher/<teacher_name>")
def teacher_stats(teacher_name: str):
    redirect_resp = _ensure_login()
    if redirect_resp:
        return redirect_resp
    data = fetch_teacher_stats(current_app.config["DB_PATH"], teacher_name)
    if not data:
        return "未找到该教师的评审记录", 404
    return render_template("teacher_stats.html", **data)


@admin_bp.route("/admin/department")
def department_stats():
    redirect_resp = _ensure_login()
    if redirect_resp:
        return redirect_resp
    data = fetch_department_stats(current_app.config["DB_PATH"])
    return render_template("department_stats.html", **data)


@admin_bp.route("/admin/export/<table_name>.csv")
def export_csv(table_name: str):
    redirect_resp = _ensure_login()
    if redirect_resp:
        return redirect_resp

    try:
        rows = export_table_rows(current_app.config["DB_PATH"], table_name)
    except ValueError:
        return "不支持的表名", 404
    if not rows:
        rows = []

    buffer = io.StringIO()
    writer = None
    for row in rows:
        if writer is None:
            writer = csv.DictWriter(buffer, fieldnames=list(row.keys()))
            writer.writeheader()
        writer.writerow(_sanitize_csv_row(row))

    if writer is None:
        buffer.write("empty\n")

    return Response(
        buffer.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={table_name}.csv"
        },
    )
