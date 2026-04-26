SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    filename TEXT,
    source_mode TEXT,
    declared_type TEXT,
    actual_type TEXT,
    department TEXT,
    teacher_name TEXT,
    course_title TEXT,
    review_round INTEGER DEFAULT 1,
    prompt_version TEXT,
    model_name TEXT,
    score_general REAL,
    score_specific REAL,
    score_total REAL,
    adjusted_score REAL,
    buffer_level TEXT,
    buffer_deduction INTEGER DEFAULT 0,
    vetoed INTEGER DEFAULT 0,
    conclusion TEXT,
    tci_total REAL,
    tci_level TEXT,
    obj_matrix_total REAL,
    obj_completeness REAL,
    obj_reasonableness REAL,
    obj_measurability REAL,
    obj_alignment REAL,
    check_log_json TEXT,
    char_count INTEGER,
    duration_sec REAL,
    issue_count INTEGER DEFAULT 0,
    fatal_count INTEGER DEFAULT 0,
    major_count INTEGER DEFAULT 0,
    minor_count INTEGER DEFAULT 0,
    note_count INTEGER DEFAULT 0,
    strengths_json TEXT,
    suggestions_json TEXT,
    structured_json TEXT,
    raw_markdown TEXT,
    status TEXT DEFAULT 'success'
);

CREATE TABLE IF NOT EXISTS record_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL,
    clause_code TEXT,
    clause_name TEXT,
    issue_category TEXT,
    issue_subcategory TEXT,
    severity TEXT,
    is_veto_related INTEGER DEFAULT 0,
    evidence_position TEXT,
    issue_text TEXT,
    suggestion_text TEXT,
    score_loss REAL,
    FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clause_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL,
    clause_code TEXT,
    clause_name TEXT,
    max_score REAL,
    actual_score REAL,
    evidence_position TEXT,
    judgment_text TEXT,
    FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS review_rounds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id INTEGER NOT NULL,
    round_number INTEGER NOT NULL,
    score_total REAL,
    major_count INTEGER,
    fatal_count INTEGER,
    conclusion TEXT,
    created_at TEXT,
    FOREIGN KEY(record_id) REFERENCES records(id) ON DELETE CASCADE
);
"""
