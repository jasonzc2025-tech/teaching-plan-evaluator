import sqlite3
from pathlib import Path
from .schema import SCHEMA_SQL


def _ensure_record_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(records)").fetchall()
    }
    alter_statements = {
        "adjusted_score": "ALTER TABLE records ADD COLUMN adjusted_score REAL",
        "buffer_level": "ALTER TABLE records ADD COLUMN buffer_level TEXT",
        "buffer_deduction": "ALTER TABLE records ADD COLUMN buffer_deduction INTEGER DEFAULT 0",
        "tci_total": "ALTER TABLE records ADD COLUMN tci_total REAL",
        "tci_level": "ALTER TABLE records ADD COLUMN tci_level TEXT",
        "obj_matrix_total": "ALTER TABLE records ADD COLUMN obj_matrix_total REAL",
        "obj_completeness": "ALTER TABLE records ADD COLUMN obj_completeness REAL",
        "obj_reasonableness": "ALTER TABLE records ADD COLUMN obj_reasonableness REAL",
        "obj_measurability": "ALTER TABLE records ADD COLUMN obj_measurability REAL",
        "obj_alignment": "ALTER TABLE records ADD COLUMN obj_alignment REAL",
        "check_log_json": "ALTER TABLE records ADD COLUMN check_log_json TEXT",
    }
    for column_name, sql in alter_statements.items():
        if column_name not in existing:
            conn.execute(sql)


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    _ensure_record_columns(conn)
    conn.commit()
    conn.close()
