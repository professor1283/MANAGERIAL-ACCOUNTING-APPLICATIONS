PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_code TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    budget_year INTEGER NOT NULL,
    difficulty TEXT NOT NULL,
    assignment_information_access TEXT NOT NULL DEFAULT 'professor_only'
        CHECK (assignment_information_access IN ('professor_only','student_and_professor')),
    assumptions_json TEXT NOT NULL,
    schedules_json TEXT NOT NULL,
    solution_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('professor','student')),
    password_hash TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    scenario_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
);


CREATE TABLE IF NOT EXISTS student_roster (
    student_id INTEGER PRIMARY KEY AUTOINCREMENT,
    professor_user_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL UNIQUE,
    student_name TEXT NOT NULL UNIQUE,
    password TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    created_at TEXT NOT NULL,
    password_created_at TEXT,
    CHECK (password IS NULL OR (length(password)=5 AND password NOT GLOB '*[^0-9]*')),
    FOREIGN KEY (professor_user_id) REFERENCES users(user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_roster_clear_log (
    clear_id INTEGER PRIMARY KEY AUTOINCREMENT,
    professor_user_id INTEGER NOT NULL,
    students_removed INTEGER NOT NULL DEFAULT 0,
    cleared_at TEXT NOT NULL,
    FOREIGN KEY (professor_user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS student_entries (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    scenario_id INTEGER NOT NULL,
    cell_key TEXT NOT NULL,
    entered_value TEXT,
    entry_type TEXT NOT NULL DEFAULT 'student_input'
        CHECK (entry_type IN ('student_input','system_calculated')),
    calculation_rule TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, scenario_id, cell_key),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
);

CREATE TABLE IF NOT EXISTS submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    scenario_id INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,
    score REAL NOT NULL,
    raw_score REAL,
    penalty_points REAL NOT NULL DEFAULT 0,
    entries_json TEXT NOT NULL,
    grading_json TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    UNIQUE (user_id, scenario_id, attempt_number),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
);

CREATE TABLE IF NOT EXISTS submission_schedule_scores (
    schedule_score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    schedule_id TEXT NOT NULL,
    schedule_title TEXT NOT NULL,
    earned_points REAL NOT NULL,
    possible_points REAL NOT NULL,
    correct_cells INTEGER NOT NULL,
    possible_cells INTEGER NOT NULL,
    FOREIGN KEY (submission_id) REFERENCES submissions(submission_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_support_events (
    support_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    scenario_id INTEGER NOT NULL,
    schedule_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('assistance','check_work')),
    penalty_points REAL NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE (user_id, scenario_id, schedule_id, event_type),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(scenario_id)
);


CREATE TABLE IF NOT EXISTS professor_settings (
    professor_user_id INTEGER NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value TEXT NOT NULL,
    PRIMARY KEY (professor_user_id, setting_key),
    FOREIGN KEY (professor_user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS dynamics_sync_log (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    local_table TEXT NOT NULL,
    local_record_id TEXT,
    dataverse_entity_set TEXT NOT NULL,
    dataverse_record_id TEXT,
    sync_direction TEXT NOT NULL CHECK (sync_direction IN ('PUSH','PULL')),
    sync_status TEXT NOT NULL CHECK (sync_status IN ('PENDING','SUCCESS','FAILED')),
    response_code INTEGER,
    response_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_roster_name ON student_roster(student_name);
CREATE INDEX IF NOT EXISTS idx_professor_settings ON professor_settings(professor_user_id, setting_key);
CREATE INDEX IF NOT EXISTS idx_roster_clear_time ON student_roster_clear_log(cleared_at);
CREATE INDEX IF NOT EXISTS idx_entries_user_scenario ON student_entries(user_id, scenario_id);
CREATE INDEX IF NOT EXISTS idx_submissions_user ON submissions(user_id, submitted_at);
CREATE INDEX IF NOT EXISTS idx_schedule_scores_submission ON submission_schedule_scores(submission_id);
CREATE INDEX IF NOT EXISTS idx_support_user_scenario ON student_support_events(user_id, scenario_id, event_type);
CREATE INDEX IF NOT EXISTS idx_audit_user_time ON audit_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sync_status ON dynamics_sync_log(sync_status, created_at);
