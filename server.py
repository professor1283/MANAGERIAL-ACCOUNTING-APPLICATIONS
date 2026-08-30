"""Zero-third-party-dependency web server for the MBA budgeting simulation."""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import math
import mimetypes
import os
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from budget_engine import ASSUMPTIONS, SCHEDULES, SOLUTION, public_assumptions, schedule_key_map
from dynamics_adapter import DataverseClient, DataverseConfig, ENTITY_SET_MAP, map_submission_to_dataverse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("BUDGET_SIM_DB", DATA_DIR / "budget_simulation.db"))
HOST = os.environ.get("BUDGET_SIM_HOST", "0.0.0.0")
PORT = int(os.environ.get("BUDGET_SIM_PORT") or os.environ.get("PORT", "8080"))
SESSION_TTL_SECONDS = 12 * 60 * 60
SESSIONS: Dict[str, Dict[str, Any]] = {}
SESSIONS_LOCK = threading.Lock()
CANVAS_EMBED = os.environ.get("BUDGET_SIM_CANVAS_EMBED", "0").strip().lower() in {"1", "true", "yes", "on"}
SECURE_COOKIES = os.environ.get("BUDGET_SIM_SECURE_COOKIES", "0").strip().lower() in {"1", "true", "yes", "on"}

STUDENT_ROSTER_NAMES = (
    "Daisy Aguilar",
    "Blhetia Bell",
    "Dewi Benham",
    "Millaun Brown",
    "Addilyn Dickerson",
    "Aerial Glasper",
    "Janya Gonzalez Galeano",
    "Tim Groenenberg",
    "Aidan Hayes",
    "Kelly Kirkland",
    "Maximus Mccarter",
    "John McCracken",
    "Aleksa Millentijevic",
    "Elliot Nixon",
    "Jullie Payne",
    "Pavle Popsavin",
    "Sofija Rajic",
    "Carson Robinette",
    "Daniel Dantema",
    "Julia Santiago",
    "Ronish Shrestha",
    "Jade Simmons",
    "Tania Varillas",
    "Mateus Vezzoni Franco",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 180_000)
    return f"pbkdf2_sha256$180000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def is_five_digit_password(password: str) -> bool:
    return len(password) == 5 and all("0" <= ch <= "9" for ch in password)


def student_username_from_name(name: str) -> str:
    base = "".join(ch.lower() if ch.isalnum() else "." for ch in name.strip())
    while ".." in base:
        base = base.replace("..", ".")
    return base.strip(".") or "student"


def ensure_roster_student(conn: sqlite3.Connection, scenario_id: int, student_name: str) -> int:
    existing_roster = conn.execute(
        "SELECT student_id, user_id FROM student_roster WHERE lower(trim(student_name))=lower(trim(?))",
        (student_name,),
    ).fetchone()
    if existing_roster:
        conn.execute(
            "UPDATE student_roster SET student_name=?, active=1 WHERE student_id=?",
            (student_name, existing_roster["student_id"]),
        )
        conn.execute(
            "UPDATE users SET display_name=?, active=1, scenario_id=? WHERE user_id=?",
            (student_name, scenario_id, existing_roster["user_id"]),
        )
        return int(existing_roster["user_id"])

    existing_user = conn.execute(
        "SELECT user_id FROM users WHERE role='student' AND lower(trim(display_name))=lower(trim(?)) ORDER BY user_id LIMIT 1",
        (student_name,),
    ).fetchone()
    if existing_user:
        user_id = int(existing_user["user_id"])
        conn.execute(
            "UPDATE users SET display_name=?, active=1, scenario_id=? WHERE user_id=?",
            (student_name, scenario_id, user_id),
        )
    else:
        base_username = student_username_from_name(student_name)
        username = base_username
        suffix = 2
        while conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            username = f"{base_username}.{suffix}"
            suffix += 1
        cur = conn.execute(
            """INSERT INTO users(username, display_name, role, password_hash, active, scenario_id, created_at)
            VALUES (?, ?, 'student', '', 1, ?, ?)""",
            (username, student_name, scenario_id, now_iso()),
        )
        user_id = int(cur.lastrowid)

    conn.execute(
        """INSERT INTO student_roster(user_id, student_name, password, active, created_at)
        VALUES (?, ?, NULL, 1, ?)""",
        (user_id, student_name, now_iso()),
    )
    return user_id


def init_db() -> None:
    schema_path = BASE_DIR / "docs" / "schema.sql"
    if not schema_path.exists():
        raise RuntimeError(f"Missing schema file: {schema_path}")
    with db_connect() as conn:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        scenario_columns = {row["name"] for row in conn.execute("PRAGMA table_info(scenarios)").fetchall()}
        if "assignment_information_access" not in scenario_columns:
            conn.execute(
                "ALTER TABLE scenarios ADD COLUMN assignment_information_access TEXT NOT NULL DEFAULT 'professor_only'"
            )
        entry_columns = {row["name"] for row in conn.execute("PRAGMA table_info(student_entries)").fetchall()}
        if "entry_type" not in entry_columns:
            conn.execute(
                "ALTER TABLE student_entries ADD COLUMN entry_type TEXT NOT NULL DEFAULT 'student_input'"
            )
        if "calculation_rule" not in entry_columns:
            conn.execute("ALTER TABLE student_entries ADD COLUMN calculation_rule TEXT")

        scenario = conn.execute("SELECT scenario_id FROM scenarios WHERE scenario_code = ?", ("NBI-2027-MBA",)).fetchone()
        if not scenario:
            cur = conn.execute(
                """INSERT INTO scenarios
                (scenario_code, company_name, budget_year, difficulty, assignment_information_access, assumptions_json, schedules_json, solution_json, active, created_at)
                VALUES (?, ?, ?, ?, 'professor_only', ?, ?, ?, 1, ?)""",
                (
                    "NBI-2027-MBA",
                    ASSUMPTIONS["company_name"],
                    ASSUMPTIONS["budget_year"],
                    ASSUMPTIONS["difficulty"],
                    json.dumps(ASSUMPTIONS),
                    json.dumps(SCHEDULES),
                    json.dumps(SOLUTION),
                    now_iso(),
                ),
            )
            scenario_id = cur.lastrowid
        else:
            scenario_id = scenario["scenario_id"]
            conn.execute(
                """UPDATE scenarios
                SET assignment_information_access='professor_only', assumptions_json=?, schedules_json=?, solution_json=?
                WHERE scenario_id=?""",
                (json.dumps(ASSUMPTIONS), json.dumps(SCHEDULES), json.dumps(SOLUTION), scenario_id),
            )

        professor_password = os.environ.get("BUDGET_SIM_PROFESSOR_PASSWORD", "3150")
        professor = conn.execute("SELECT user_id FROM users WHERE username='professor'").fetchone()
        if not professor:
            conn.execute(
                """INSERT INTO users
                (username, display_name, role, password_hash, active, scenario_id, created_at)
                VALUES ('professor', 'Professor', 'professor', ?, 1, ?, ?)""",
                (hash_password(professor_password), scenario_id, now_iso()),
            )
        else:
            conn.execute(
                "UPDATE users SET display_name='Professor', role='professor', active=1, scenario_id=? WHERE user_id=?",
                (scenario_id, professor["user_id"]),
            )

        # The former demonstration student is no longer a valid student-access path.
        conn.execute("UPDATE users SET active=0 WHERE username='mba.student' AND role='student'")

        for student_name in STUDENT_ROSTER_NAMES:
            ensure_roster_student(conn, scenario_id, student_name)
        settings = {
            "max_attempts": "3",
            "passing_score": "80",
            "allow_student_feedback": "1",
        }
        for key, value in settings.items():
            conn.execute("INSERT OR IGNORE INTO app_settings(setting_key, setting_value) VALUES (?, ?)", (key, value))
        conn.commit()


def session_cookie(token: str, *, delete: bool = False) -> str:
    """Build the login cookie without changing the application's default local behavior.

    Canvas iframe launches are cross-site. When BUDGET_SIM_CANVAS_EMBED=1,
    SameSite=None and Secure are used so browsers may send the session cookie
    inside an HTTPS Canvas frame. Standalone/local launches remain SameSite=Lax.
    """
    same_site = "None" if CANVAS_EMBED else "Lax"
    secure = CANVAS_EMBED or SECURE_COOKIES
    value = "" if delete else token
    max_age = 0 if delete else SESSION_TTL_SECONDS
    parts = [f"budget_session={value}", "Path=/", "HttpOnly", f"SameSite={same_site}", f"Max-Age={max_age}"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clean_sessions() -> None:
    cutoff = time.time() - SESSION_TTL_SECONDS
    with SESSIONS_LOCK:
        expired = [token for token, data in SESSIONS.items() if data["created"] < cutoff]
        for token in expired:
            SESSIONS.pop(token, None)


def make_session(user: sqlite3.Row) -> str:
    clean_sessions()
    token = secrets.token_urlsafe(32)
    with SESSIONS_LOCK:
        SESSIONS[token] = {
            "user_id": user["user_id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
            "scenario_id": user["scenario_id"],
            "created": time.time(),
        }
    return token


def get_setting(conn: sqlite3.Connection, key: str, default: str) -> str:
    row = conn.execute("SELECT setting_value FROM app_settings WHERE setting_key=?", (key,)).fetchone()
    return row["setting_value"] if row else default


def get_key_formats() -> Dict[str, str]:
    result: Dict[str, str] = {}
    for schedule in SCHEDULES:
        for row in schedule["rows"]:
            for cell in row["cells"]:
                if cell.get("key"):
                    result[cell["key"]] = cell.get("format", "currency")
    return result


KEY_FORMATS = get_key_formats()
SCHEDULE_KEYS = schedule_key_map()

SALES_INPUT_KEYS = {f"sales.units.{q}" for q in ("Q1", "Q2", "Q3", "Q4")}
SYSTEM_CALCULATED_KEYS = {"sales.units.Total", *(f"sales.revenue.{c}" for c in ("Q1", "Q2", "Q3", "Q4", "Total"))}
CALCULATION_RULES = {
    "sales.units.Total": "SUM(sales.units.Q1:sales.units.Q4)",
    **{f"sales.revenue.{q}": f"sales.units.{q} * selling_price_per_unit" for q in ("Q1", "Q2", "Q3", "Q4")},
    "sales.revenue.Total": "sales.units.Total * selling_price_per_unit",
}

def normalize_entries(entries: Dict[str, Any]) -> Dict[str, Any]:
    """Recalculate protected sales-budget fields from student unit-sales inputs."""
    normalized = dict(entries)
    units: Dict[str, float] = {}
    complete = True
    for quarter in ("Q1", "Q2", "Q3", "Q4"):
        key = f"sales.units.{quarter}"
        try:
            raw = normalized.get(key)
            if raw is None or str(raw).strip() == "":
                raise ValueError
            units[quarter] = float(raw)
            if not math.isfinite(units[quarter]):
                raise ValueError
        except (TypeError, ValueError):
            complete = False
            normalized.pop(f"sales.revenue.{quarter}", None)
    price = float(ASSUMPTIONS["selling_price"])
    for quarter, amount in units.items():
        normalized[f"sales.revenue.{quarter}"] = round(amount * price, 2)
    if complete:
        total_units = sum(units.values())
        normalized["sales.units.Total"] = round(total_units, 2)
        normalized["sales.revenue.Total"] = round(total_units * price, 2)
    else:
        normalized.pop("sales.units.Total", None)
        normalized.pop("sales.revenue.Total", None)
    return normalized


def grade_entries(entries: Dict[str, Any]) -> Dict[str, Any]:
    entries = normalize_entries(entries)
    schedule_results: Dict[str, Any] = {}
    total_score = 0.0
    details: Dict[str, Any] = {}

    for schedule in SCHEDULES:
        sid = schedule["id"]
        keys = SCHEDULE_KEYS[sid]
        correct = 0
        for key in keys:
            expected = float(SOLUTION[key])
            raw = entries.get(key)
            try:
                actual = float(raw)
                fmt = KEY_FORMATS.get(key, "currency")
                tolerance = 0.5 if fmt in {"units", "hours"} else 1.0
                is_correct = abs(actual - expected) <= tolerance
            except (TypeError, ValueError):
                actual = None
                is_correct = False
            if is_correct:
                correct += 1
            details[key] = {
                "actual": actual,
                "expected": expected,
                "correct": is_correct,
                "format": KEY_FORMATS.get(key, "currency"),
            }
        earned = schedule["weight"] * (correct / len(keys) if keys else 1)
        total_score += earned
        schedule_results[sid] = {
            "title": schedule["title"],
            "weight": schedule["weight"],
            "correct": correct,
            "possible_cells": len(keys),
            "score": round(earned, 2),
        }
    return {
        "score": round(total_score, 2),
        "schedule_results": schedule_results,
        "details": details,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "BudgetSimulation/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write(f"[{now_iso()}] {self.address_string()} - {fmt % args}\n")

    def _cookies(self) -> SimpleCookie:
        cookie = SimpleCookie()
        if self.headers.get("Cookie"):
            cookie.load(self.headers.get("Cookie"))
        return cookie

    def _session(self) -> Optional[Dict[str, Any]]:
        clean_sessions()
        morsel = self._cookies().get("budget_session")
        if not morsel:
            return None
        with SESSIONS_LOCK:
            return SESSIONS.get(morsel.value)

    def _json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _send_json(self, payload: Any, status: int = 200, cookies: list[str] | None = None) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookies:
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _require(self, role: str | None = None) -> Optional[Dict[str, Any]]:
        session = self._session()
        if not session:
            self._send_json({"error": "Authentication required"}, 401)
            return None
        if role and session["role"] != role:
            self._send_json({"error": "Insufficient permission"}, 403)
            return None
        return session

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/"):
            self._api_get(path, urllib.parse.parse_qs(parsed.query))
        else:
            self._serve_static(path)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        self._api_post(parsed.path, self._json_body())

    def _api_get(self, path: str, query: Dict[str, Any]) -> None:
        if path == "/api/health":
            self._send_json({"status": "ok", "database": str(DB_PATH.name), "time": now_iso()})
            return
        if path == "/api/session":
            session = self._session()
            self._send_json({"authenticated": bool(session), "user": session})
            return
        if path == "/api/scenario":
            session = self._require()
            if not session:
                return
            with db_connect() as conn:
                scenario = conn.execute("SELECT * FROM scenarios WHERE scenario_id=?", (session["scenario_id"],)).fetchone()
            self._send_json({
                "scenario": {
                    "scenario_code": scenario["scenario_code"],
                    "company_name": scenario["company_name"],
                    "budget_year": scenario["budget_year"],
                    "difficulty": scenario["difficulty"],
                    "assignment_information_access": scenario["assignment_information_access"],
                    "assumptions": public_assumptions() if session["role"] == "professor" else [],
                    "schedules": json.loads(scenario["schedules_json"]),
                }
            })
            return
        if path == "/api/professor/assignment":
            session = self._require("professor")
            if not session:
                return
            with db_connect() as conn:
                scenario = conn.execute("SELECT * FROM scenarios WHERE scenario_id=?", (session["scenario_id"],)).fetchone()
            self._send_json({
                "scenario": {
                    "scenario_code": scenario["scenario_code"],
                    "company_name": scenario["company_name"],
                    "budget_year": scenario["budget_year"],
                    "difficulty": scenario["difficulty"],
                    "assignment_information_access": scenario["assignment_information_access"],
                    "assumptions": public_assumptions(),
                    "schedules": json.loads(scenario["schedules_json"]),
                }
            })
            return
        if path == "/api/student/work":
            session = self._require("student")
            if not session:
                return
            with db_connect() as conn:
                rows = conn.execute("SELECT cell_key, entered_value FROM student_entries WHERE user_id=?", (session["user_id"],)).fetchall()
                attempts = conn.execute("SELECT COUNT(*) AS c FROM submissions WHERE user_id=?", (session["user_id"],)).fetchone()["c"]
                max_attempts = int(get_setting(conn, "max_attempts", "3"))
                latest = conn.execute("SELECT submission_id, score, submitted_at FROM submissions WHERE user_id=? ORDER BY submission_id DESC LIMIT 1", (session["user_id"],)).fetchone()
            self._send_json({
                "entries": {r["cell_key"]: r["entered_value"] for r in rows},
                "attempts_used": attempts,
                "max_attempts": max_attempts,
                "latest": dict(latest) if latest else None,
            })
            return
        if path == "/api/student/results":
            session = self._require("student")
            if not session:
                return
            with db_connect() as conn:
                submission = conn.execute("SELECT * FROM submissions WHERE user_id=? ORDER BY submission_id DESC LIMIT 1", (session["user_id"],)).fetchone()
                allow_feedback = get_setting(conn, "allow_student_feedback", "1") == "1"
                if not submission:
                    self._send_json({"submission": None})
                    return
                details = json.loads(submission["grading_json"])
                if not allow_feedback:
                    details.pop("details", None)
            self._send_json({"submission": {**dict(submission), "grading": details}})
            return
        if path == "/api/professor/students":
            session = self._require("professor")
            if not session:
                return
            with db_connect() as conn:
                rows = conn.execute(
                    """SELECT u.user_id, u.username, sr.student_name AS display_name, sr.password, sr.password_created_at, sr.active,
                    COUNT(s.submission_id) AS attempts,
                    MAX(s.score) AS best_score,
                    MAX(s.submitted_at) AS last_submitted
                    FROM student_roster sr
                    JOIN users u ON u.user_id=sr.user_id
                    LEFT JOIN submissions s ON s.user_id=u.user_id
                    WHERE sr.active=1
                    GROUP BY sr.student_id, u.user_id
                    ORDER BY sr.student_name"""
                ).fetchall()
                settings = {r["setting_key"]: r["setting_value"] for r in conn.execute("SELECT * FROM app_settings")}
            self._send_json({"students": [dict(r) for r in rows], "settings": settings})
            return
        if path == "/api/professor/submissions":
            session = self._require("professor")
            if not session:
                return
            with db_connect() as conn:
                rows = conn.execute(
                    """SELECT s.submission_id, s.attempt_number, s.score, s.submitted_at,
                    u.username, u.display_name
                    FROM submissions s JOIN users u ON u.user_id=s.user_id
                    ORDER BY s.submitted_at DESC"""
                ).fetchall()
            self._send_json({"submissions": [dict(r) for r in rows]})
            return
        if path == "/api/professor/solution":
            session = self._require("professor")
            if not session:
                return
            self._send_json({"solution": SOLUTION, "schedules": SCHEDULES})
            return
        if path == "/api/professor/dynamics/status":
            session = self._require("professor")
            if not session:
                return
            configured = bool(os.environ.get("DATAVERSE_URL") and os.environ.get("DATAVERSE_ACCESS_TOKEN"))
            with db_connect() as conn:
                unsynced = conn.execute(
                    """SELECT COUNT(*) AS c FROM submissions s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM dynamics_sync_log d
                        WHERE d.local_table='submissions'
                        AND d.local_record_id=CAST(s.submission_id AS TEXT)
                        AND d.sync_status='SUCCESS'
                    )"""
                ).fetchone()["c"]
                last_sync = conn.execute(
                    "SELECT sync_status, response_message, created_at FROM dynamics_sync_log ORDER BY sync_id DESC LIMIT 1"
                ).fetchone()
            self._send_json({
                "configured": configured,
                "organization_url": os.environ.get("DATAVERSE_URL", ""),
                "api_version": "v9.2",
                "unsynced_submissions": unsynced,
                "last_sync": dict(last_sync) if last_sync else None,
            })
            return
        if path == "/api/professor/export.csv":
            session = self._require("professor")
            if not session:
                return
            with db_connect() as conn:
                rows = conn.execute(
                    """SELECT u.username, u.display_name, s.attempt_number, s.score, s.submitted_at
                    FROM submissions s JOIN users u ON u.user_id=s.user_id
                    ORDER BY u.display_name, s.attempt_number"""
                ).fetchall()
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Username", "Student Name", "Attempt", "Score", "Submitted At (UTC)"])
            for r in rows:
                writer.writerow([r["username"], r["display_name"], r["attempt_number"], r["score"], r["submitted_at"]])
            body = output.getvalue().encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="budget_simulation_scores.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_json({"error": "API route not found"}, 404)

    def _api_post(self, path: str, data: Dict[str, Any]) -> None:
        if path == "/api/login":
            login_name = str(data.get("name", data.get("username", ""))).strip()
            password = str(data.get("password", ""))
            password_created = False
            with db_connect() as conn:
                if login_name.lower() == "professor":
                    user = conn.execute("SELECT * FROM users WHERE username='professor' AND active=1").fetchone()
                    if not user or not verify_password(password, user["password_hash"] or ""):
                        self._send_json({"error": "Invalid professor name or password"}, 401)
                        return
                else:
                    if not is_five_digit_password(password):
                        self._send_json({"error": "Student passwords must contain exactly five numerical digits"}, 400)
                        return
                    roster = conn.execute(
                        """SELECT sr.*, u.* FROM student_roster sr
                        JOIN users u ON u.user_id=sr.user_id
                        WHERE sr.active=1 AND u.active=1
                        AND lower(trim(sr.student_name))=lower(trim(?))
                        LIMIT 1""",
                        (login_name,),
                    ).fetchone()
                    if not roster:
                        self._send_json({"error": "Student name was not found on the authorized class roster"}, 401)
                        return
                    stored_password = roster["password"]
                    if stored_password is None or str(stored_password) == "":
                        conn.execute(
                            "UPDATE student_roster SET password=?, password_created_at=? WHERE student_id=?",
                            (password, now_iso(), roster["student_id"]),
                        )
                        password_created = True
                    elif not hmac.compare_digest(str(stored_password), password):
                        self._send_json({"error": "Invalid student name or password"}, 401)
                        return
                    user = conn.execute("SELECT * FROM users WHERE user_id=? AND active=1", (roster["user_id"],)).fetchone()
                    if not user:
                        self._send_json({"error": "Student account is inactive"}, 403)
                        return
                conn.execute(
                    "INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, ?, ?, ?)",
                    (
                        user["user_id"],
                        "STUDENT_PASSWORD_CREATED" if password_created else "LOGIN",
                        json.dumps({"ip": self.client_address[0]}),
                        now_iso(),
                    ),
                )
                conn.commit()
            token = make_session(user)
            self._send_json(
                {
                    "ok": True,
                    "password_created": password_created,
                    "user": {"username": user["username"], "display_name": user["display_name"], "role": user["role"]},
                },
                cookies=[session_cookie(token)],
            )
            return
        if path == "/api/logout":
            morsel = self._cookies().get("budget_session")
            if morsel:
                with SESSIONS_LOCK:
                    SESSIONS.pop(morsel.value, None)
            self._send_json({"ok": True}, cookies=[session_cookie("", delete=True)])
            return
        if path == "/api/student/save":
            session = self._require("student")
            if not session:
                return
            entries = data.get("entries", {})
            if not isinstance(entries, dict):
                self._send_json({"error": "entries must be an object"}, 400)
                return
            entries = normalize_entries(entries)
            valid_keys = set(SOLUTION)
            with db_connect() as conn:
                for calculated_key in SYSTEM_CALCULATED_KEYS:
                    if calculated_key not in entries:
                        conn.execute(
                            "DELETE FROM student_entries WHERE user_id=? AND scenario_id=? AND cell_key=?",
                            (session["user_id"], session["scenario_id"], calculated_key),
                        )
                for key, value in entries.items():
                    if key not in valid_keys:
                        continue
                    value_text = "" if value is None else str(value).strip()
                    entry_type = "system_calculated" if key in SYSTEM_CALCULATED_KEYS else "student_input"
                    calculation_rule = CALCULATION_RULES.get(key)
                    conn.execute(
                        """INSERT INTO student_entries
                        (user_id, scenario_id, cell_key, entered_value, entry_type, calculation_rule, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(user_id, scenario_id, cell_key)
                        DO UPDATE SET entered_value=excluded.entered_value, entry_type=excluded.entry_type,
                                      calculation_rule=excluded.calculation_rule, updated_at=excluded.updated_at""",
                        (session["user_id"], session["scenario_id"], key, value_text, entry_type, calculation_rule, now_iso()),
                    )
                conn.execute("INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'SAVE_DRAFT', ?, ?)", (session["user_id"], json.dumps({"cell_count": len(entries)}), now_iso()))
                conn.commit()
            self._send_json({"ok": True, "saved_at": now_iso()})
            return
        if path == "/api/student/submit":
            session = self._require("student")
            if not session:
                return
            entries = data.get("entries", {})
            if not isinstance(entries, dict):
                self._send_json({"error": "entries must be an object"}, 400)
                return
            entries = normalize_entries(entries)
            with db_connect() as conn:
                attempts = conn.execute("SELECT COUNT(*) AS c FROM submissions WHERE user_id=?", (session["user_id"],)).fetchone()["c"]
                max_attempts = int(get_setting(conn, "max_attempts", "3"))
                if attempts >= max_attempts:
                    self._send_json({"error": "Maximum number of attempts reached"}, 409)
                    return
                grading = grade_entries(entries)
                attempt_no = attempts + 1
                cur = conn.execute(
                    """INSERT INTO submissions
                    (user_id, scenario_id, attempt_number, score, entries_json, grading_json, submitted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session["user_id"], session["scenario_id"], attempt_no, grading["score"], json.dumps(entries), json.dumps(grading), now_iso()),
                )
                submission_id = cur.lastrowid
                for sid, result in grading["schedule_results"].items():
                    conn.execute(
                        """INSERT INTO submission_schedule_scores
                        (submission_id, schedule_id, schedule_title, earned_points, possible_points, correct_cells, possible_cells)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (submission_id, sid, result["title"], result["score"], result["weight"], result["correct"], result["possible_cells"]),
                    )
                conn.execute("INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'SUBMIT', ?, ?)", (session["user_id"], json.dumps({"attempt": attempt_no, "score": grading["score"]}), now_iso()))
                conn.commit()
            self._send_json({"ok": True, "submission_id": submission_id, "attempt_number": attempt_no, "grading": grading})
            return
        if path == "/api/professor/students":
            session = self._require("professor")
            if not session:
                return
            display_name = str(data.get("display_name", "")).strip()
            if not display_name:
                self._send_json({"error": "Student name is required"}, 400)
                return
            try:
                with db_connect() as conn:
                    if conn.execute(
                        "SELECT 1 FROM student_roster WHERE lower(trim(student_name))=lower(trim(?))",
                        (display_name,),
                    ).fetchone():
                        self._send_json({"error": "That student is already in the Student Table"}, 409)
                        return
                    ensure_roster_student(conn, session["scenario_id"], display_name)
                    conn.execute(
                        "INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'PROFESSOR_ADD_STUDENT', ?, ?)",
                        (session["user_id"], json.dumps({"student_name": display_name}), now_iso()),
                    )
                    conn.commit()
            except sqlite3.IntegrityError:
                self._send_json({"error": "That student could not be added"}, 409)
                return
            self._send_json({"ok": True})
            return
        if path == "/api/professor/reset":
            session = self._require("professor")
            if not session:
                return
            try:
                user_id = int(data.get("user_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "Valid user_id required"}, 400)
                return
            with db_connect() as conn:
                conn.execute("DELETE FROM submission_schedule_scores WHERE submission_id IN (SELECT submission_id FROM submissions WHERE user_id=?)", (user_id,))
                conn.execute("DELETE FROM submissions WHERE user_id=?", (user_id,))
                conn.execute("DELETE FROM student_entries WHERE user_id=?", (user_id,))
                conn.execute("INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'PROFESSOR_RESET', ?, ?)", (session["user_id"], json.dumps({"student_user_id": user_id}), now_iso()))
                conn.commit()
            self._send_json({"ok": True})
            return
        if path == "/api/professor/settings":
            session = self._require("professor")
            if not session:
                return
            allowed = {"max_attempts", "passing_score", "allow_student_feedback"}
            with db_connect() as conn:
                for key, value in data.items():
                    if key in allowed:
                        conn.execute("INSERT INTO app_settings(setting_key, setting_value) VALUES (?, ?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value", (key, str(value)))
                conn.commit()
            self._send_json({"ok": True})
            return
        if path == "/api/professor/dynamics/push":
            session = self._require("professor")
            if not session:
                return
            try:
                client = DataverseClient(DataverseConfig.from_environment())
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, 409)
                return
            pushed = 0
            failed = 0
            with db_connect() as conn:
                rows = conn.execute(
                    """SELECT s.*, u.username, u.display_name
                    FROM submissions s JOIN users u ON u.user_id=s.user_id
                    WHERE NOT EXISTS (
                        SELECT 1 FROM dynamics_sync_log d
                        WHERE d.local_table='submissions'
                        AND d.local_record_id=CAST(s.submission_id AS TEXT)
                        AND d.sync_status='SUCCESS'
                    )
                    ORDER BY s.submission_id"""
                ).fetchall()
                for row in rows:
                    submission = dict(row)
                    student = {"username": row["username"], "display_name": row["display_name"]}
                    try:
                        result = client.create_row(ENTITY_SET_MAP["submissions"], map_submission_to_dataverse(submission, student))
                        entity_id = result.get("headers", {}).get("OData-EntityId", "")
                        conn.execute(
                            """INSERT INTO dynamics_sync_log
                            (user_id, local_table, local_record_id, dataverse_entity_set, dataverse_record_id, sync_direction, sync_status, response_code, response_message, created_at)
                            VALUES (?, 'submissions', ?, ?, ?, 'PUSH', 'SUCCESS', ?, ?, ?)""",
                            (session["user_id"], str(row["submission_id"]), ENTITY_SET_MAP["submissions"], entity_id, result.get("status"), "Submission pushed to Dataverse", now_iso()),
                        )
                        pushed += 1
                    except Exception as exc:
                        conn.execute(
                            """INSERT INTO dynamics_sync_log
                            (user_id, local_table, local_record_id, dataverse_entity_set, sync_direction, sync_status, response_message, created_at)
                            VALUES (?, 'submissions', ?, ?, 'PUSH', 'FAILED', ?, ?)""",
                            (session["user_id"], str(row["submission_id"]), ENTITY_SET_MAP["submissions"], str(exc)[:2000], now_iso()),
                        )
                        failed += 1
                conn.commit()
            self._send_json({"ok": failed == 0, "pushed": pushed, "failed": failed})
            return
        self._send_json({"error": "API route not found"}, 404)

    def _serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        safe = Path(urllib.parse.unquote(path.lstrip("/")))
        if ".." in safe.parts:
            self._send_text("Not found", 404)
            return
        target = (STATIC_DIR / safe).resolve()
        if STATIC_DIR.resolve() not in target.parents and target != STATIC_DIR.resolve():
            self._send_text("Not found", 404)
            return
        if not target.exists() or not target.is_file():
            target = STATIC_DIR / "index.html"
        content = target.read_bytes()
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype == "application/javascript" else ""))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)


def run() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print("\nNorthbridge Components MBA Budget Simulation")
    print(f"Open locally: {url}")
    print(f"Network access: http://<this-computer-IP>:{PORT}")
    print("Professor login name: Professor")
    print(f"Student roster loaded: {len(STUDENT_ROSTER_NAMES)} students; first login creates a five-digit numerical password")
    print("Press Ctrl+C to stop.\n")
    if os.environ.get("BUDGET_SIM_NO_BROWSER") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
