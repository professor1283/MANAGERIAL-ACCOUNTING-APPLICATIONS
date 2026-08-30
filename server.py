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
import unicodedata
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

PROFESSOR_LOGIN_MAP = {
    "professor": "professor",
    "professor 1": "professor1",
    "professor 2": "professor2",
}

SUPPORT_GUIDE = {'sales': {'explanation': 'The sales budget is the starting point for the master budget because expected unit sales drive production, purchases, labor, overhead, cash collections, and several financial-statement amounts. Enter the forecasted units for each quarter. The application calculates annual units and sales revenue from the unit forecast and the stated selling price. A common error is to confuse unit sales with dollar sales or to type the selling price into a unit-sales cell.', 'assistance': 'Work from the quarterly sales forecast in the assignment information. Enter Q1 through Q4 budgeted unit sales only. The annual unit total is the sum of the four quarters. Budgeted sales revenue for a quarter equals budgeted unit sales multiplied by selling price per unit. The application calculates the revenue cells automatically, so verify the unit inputs first.'}, 'collections': {'explanation': 'The cash collections budget converts accrual-basis sales into expected cash receipts. Each quarter generally contains cash collected from current-quarter sales plus collections related to the preceding quarter. Beginning accounts receivable represents prior-period sales that are collected in the first quarter. Ending accounts receivable represents the portion of fourth-quarter sales that will not be collected until the following year.', 'assistance': 'For each quarter, separate collections into two layers: current-quarter sales multiplied by the current-quarter collection percentage, and prior-quarter sales multiplied by the following-quarter percentage. In Q1, use beginning accounts receivable for the prior-period component. Add the two layers for total collections. Year-end accounts receivable is the uncollected portion of Q4 sales.'}, 'production': {'explanation': 'The production budget determines how many units must be manufactured to satisfy sales demand while maintaining the required finished-goods inventory. Production is not automatically equal to sales because beginning and desired ending inventory change the number of units that must be produced.', 'assistance': "Use this sequence for each quarter: budgeted unit sales + desired ending finished-goods units = total unit requirements; then subtract beginning finished-goods units to obtain required production. Desired ending finished goods equals the stated percentage of the next quarter's unit sales. The next quarter's beginning finished goods equals the previous quarter's ending finished goods."}, 'materials': {'explanation': 'The direct-materials budget converts production units into kilograms of material needed, incorporates the raw-material inventory policy, determines purchases, and then converts purchases into cash payments. Purchases and cash payments differ because suppliers are paid over more than one quarter.', 'assistance': 'First multiply required production units by kilograms required per finished unit. Add desired ending raw-material inventory, then subtract beginning raw-material inventory to obtain required purchases in kilograms. Multiply purchase kilograms by cost per kilogram for purchase cost. For cash payments, apply the supplier-payment percentages to current and prior-quarter purchases; include beginning accounts payable in Q1.'}, 'labor': {'explanation': 'The direct-labor budget converts production activity into labor hours and labor cost. It is driven by production, not sales, because employees work on the units manufactured during the period.', 'assistance': 'For each quarter, multiply required production units by direct-labor hours per unit to obtain required hours. Then multiply required direct-labor hours by the hourly wage rate to obtain direct-labor cost. Annual totals are the sum of the quarterly amounts.'}, 'moh': {'explanation': 'The manufacturing-overhead budget separates overhead that varies with activity from fixed manufacturing overhead. Depreciation is included in total overhead for product costing but is removed when determining cash overhead because depreciation does not require a current cash payment.', 'assistance': 'Calculate variable manufacturing overhead as direct-labor hours multiplied by the variable overhead rate. Add quarterly fixed manufacturing overhead to obtain total manufacturing overhead. Subtract the depreciation component of fixed overhead to obtain cash manufacturing overhead.'}, 'inventory': {'explanation': 'This schedule applies absorption costing. A finished unit includes direct materials, direct labor, variable manufacturing overhead, and an allocation of fixed manufacturing overhead. Those unit costs are then used to value ending finished goods and support cost of goods manufactured and cost of goods sold.', 'assistance': 'Build unit product cost one component at a time: material quantity per unit x material price; labor hours per unit x labor rate; labor hours per unit x variable-overhead rate; and annual fixed manufacturing overhead divided by annual production units. Add the four components for unit product cost. Use ending quantities to value inventories, then reconcile beginning finished goods + cost of goods manufactured - ending finished goods to cost of goods sold.'}, 'sga': {'explanation': 'The selling, general, and administrative budget combines a variable component tied to sales dollars with fixed SG&A. As with manufacturing overhead, depreciation belongs in expense but is removed when computing the cash portion of SG&A.', 'assistance': 'For each quarter, multiply budgeted sales revenue by the variable SG&A percentage. Add quarterly fixed SG&A to obtain total SG&A expense. Subtract the SG&A depreciation amount to obtain cash SG&A.'}, 'cash': {'explanation': 'The cash and financing schedule integrates cash receipts and cash disbursements and then determines whether short-term borrowing or repayment is required to maintain the minimum cash balance. Interest is based on beginning-of-quarter debt, so the financing sequence matters.', 'assistance': 'Begin with beginning cash and add cash collections to get total cash available. Deduct all current-quarter cash disbursements, including materials, labor, cash overhead, cash SG&A, capital expenditures, taxes, interest, and dividends. Compare cash before financing with the minimum balance. Borrow or repay only in the specified increments, then compute ending cash and ending line-of-credit balance.'}, 'income': {'explanation': 'The pro-forma income statement summarizes the expected accrual-basis operating results. It uses sales and absorption-costing cost of goods sold, then deducts SG&A, interest, and income tax expense to arrive at budgeted net income.', 'assistance': 'Follow the income-statement sequence: sales - cost of goods sold = gross margin; gross margin - SG&A = operating income; operating income - interest = income before taxes; subtract income tax expense to obtain net income. Quarterly amounts should reconcile to the annual totals.'}, 'balance': {'explanation': 'The pro-forma balance sheet presents the expected year-end financial position. Many amounts come directly from the ending balances produced by earlier budgets. Retained earnings also incorporates budgeted net income and dividends. The accounting equation must balance.', 'assistance': "Use year-end balances from the supporting schedules for cash, receivables, inventories, accounts payable, and line of credit. Gross PPE equals beginning gross PPE plus capital expenditures. Accumulated depreciation includes beginning accumulated depreciation plus current-year depreciation and is entered as a positive contra-asset amount. Finish by verifying Total Assets = Total Liabilities + Stockholders' Equity."}, 'cashflow': {'explanation': 'The indirect-method statement of cash flows begins with net income and adjusts for noncash expenses and changes in working capital to derive operating cash flow. Investing and financing activities are then reported separately, and the resulting net change must reconcile beginning cash to ending cash.', 'assistance': 'Start operating activities with net income, add depreciation, then adjust for changes in receivables, inventories, and payables using the signs specified in the instructions. Capital expenditures belong in investing activities. Borrowings, debt repayments, and dividends belong in financing activities. Add the three sections to obtain net change in cash and reconcile beginning cash to ending cash.'}}


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


def ensure_roster_student(conn: sqlite3.Connection, scenario_id: int, professor_user_id: int, student_name: str) -> int:
    """Create or reactivate a student inside one professor-owned roster.

    Student names remain globally unique so the student login screen can remain unchanged:
    students still enter only their name and five-digit password, with no professor selector.
    """
    existing_roster = conn.execute(
        "SELECT student_id, user_id, professor_user_id FROM student_roster WHERE lower(trim(student_name))=lower(trim(?))",
        (student_name,),
    ).fetchone()
    if existing_roster:
        if int(existing_roster["professor_user_id"]) != int(professor_user_id):
            raise sqlite3.IntegrityError("Student name is already assigned to another professor")
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
        """INSERT INTO student_roster(professor_user_id, user_id, student_name, password, active, created_at)
        VALUES (?, ?, ?, NULL, 1, ?)""",
        (professor_user_id, user_id, student_name, now_iso()),
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

        submission_columns = {row["name"] for row in conn.execute("PRAGMA table_info(submissions)").fetchall()}
        if "raw_score" not in submission_columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN raw_score REAL")
        if "penalty_points" not in submission_columns:
            conn.execute("ALTER TABLE submissions ADD COLUMN penalty_points REAL NOT NULL DEFAULT 0")
        conn.execute("UPDATE submissions SET raw_score=score WHERE raw_score IS NULL")

        # Upgrade prior semester databases to professor-owned student rosters.
        roster_columns = {row["name"] for row in conn.execute("PRAGMA table_info(student_roster)").fetchall()}
        if "professor_user_id" not in roster_columns:
            conn.execute("ALTER TABLE student_roster ADD COLUMN professor_user_id INTEGER")

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
        professor_accounts = (
            ("professor", "Professor", professor_password),
            ("professor1", "Professor 1", "12345"),
            ("professor2", "Professor 2", "12345"),
        )
        professor_ids: Dict[str, int] = {}
        for username, display_name, initial_password in professor_accounts:
            professor = conn.execute("SELECT user_id FROM users WHERE username=?", (username,)).fetchone()
            if not professor:
                cur = conn.execute(
                    """INSERT INTO users
                    (username, display_name, role, password_hash, active, scenario_id, created_at)
                    VALUES (?, ?, 'professor', ?, 1, ?, ?)""",
                    (username, display_name, hash_password(initial_password), scenario_id, now_iso()),
                )
                professor_ids[username] = int(cur.lastrowid)
            else:
                conn.execute(
                    "UPDATE users SET display_name=?, role='professor', active=1, scenario_id=? WHERE user_id=?",
                    (display_name, scenario_id, professor["user_id"]),
                )
                professor_ids[username] = int(professor["user_id"])

        # Existing student records from earlier versions belong to the original Professor.
        conn.execute(
            "UPDATE student_roster SET professor_user_id=? WHERE professor_user_id IS NULL",
            (professor_ids["professor"],),
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_roster_professor ON student_roster(professor_user_id, student_name)"
        )

        # The former demonstration student is no longer a valid student-access path.
        conn.execute("UPDATE users SET active=0 WHERE username='mba.student' AND role='student'")

        default_professor_settings = {
            "max_attempts": "3",
            "passing_score": "80",
            "allow_student_feedback": "1",
            "check_work_enabled": "1",
            "check_work_penalty": "1",
            "assistance_penalty": "1",
        }
        # Preserve any settings from the former single-professor version for the
        # original Professor account during migration.
        legacy_settings = {
            row["setting_key"]: row["setting_value"]
            for row in conn.execute(
                "SELECT setting_key, setting_value FROM app_settings WHERE setting_key IN ('max_attempts','passing_score','allow_student_feedback')"
            )
        }
        for professor_user_id in professor_ids.values():
            for key, value in default_professor_settings.items():
                conn.execute(
                    """INSERT OR IGNORE INTO professor_settings
                    (professor_user_id, setting_key, setting_value)
                    VALUES (?, ?, ?)""",
                    (professor_user_id, key, value),
                )
        for key, value in legacy_settings.items():
            conn.execute(
                """INSERT INTO professor_settings(professor_user_id, setting_key, setting_value)
                VALUES (?, ?, ?)
                ON CONFLICT(professor_user_id, setting_key) DO UPDATE SET setting_value=excluded.setting_value""",
                (professor_ids["professor"], key, value),
            )

        # Seed the supplied roster once into the original Professor's independent table.
        # Professor 1 and Professor 2 begin with independent empty tables, preserving the
        # existing student login method (student name + five-digit password, no section selector).
        roster_seeded = conn.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key='student_roster_seeded'"
        ).fetchone()
        if roster_seeded is None:
            for student_name in STUDENT_ROSTER_NAMES:
                ensure_roster_student(conn, scenario_id, professor_ids["professor"], student_name)
            conn.execute(
                "INSERT INTO app_settings(setting_key, setting_value) VALUES ('student_roster_seeded', '1')"
            )
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
    """Read a legacy/global application setting."""
    row = conn.execute("SELECT setting_value FROM app_settings WHERE setting_key=?", (key,)).fetchone()
    return row["setting_value"] if row else default


def get_professor_setting(conn: sqlite3.Connection, professor_user_id: int, key: str, default: str) -> str:
    row = conn.execute(
        "SELECT setting_value FROM professor_settings WHERE professor_user_id=? AND setting_key=?",
        (professor_user_id, key),
    ).fetchone()
    return row["setting_value"] if row else default


def get_student_professor_id(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute(
        "SELECT professor_user_id FROM student_roster WHERE user_id=? AND active=1",
        (user_id,),
    ).fetchone()
    if not row or row["professor_user_id"] is None:
        raise RuntimeError("Student is not assigned to an active professor roster")
    return int(row["professor_user_id"])


def get_student_policy(conn: sqlite3.Connection, user_id: int) -> Dict[str, Any]:
    professor_user_id = get_student_professor_id(conn, user_id)
    return {
        "professor_user_id": professor_user_id,
        "max_attempts": int(get_professor_setting(conn, professor_user_id, "max_attempts", "3")),
        "passing_score": float(get_professor_setting(conn, professor_user_id, "passing_score", "80")),
        "allow_student_feedback": get_professor_setting(conn, professor_user_id, "allow_student_feedback", "1") == "1",
        "check_work_enabled": get_professor_setting(conn, professor_user_id, "check_work_enabled", "1") == "1",
        "check_work_penalty": float(get_professor_setting(conn, professor_user_id, "check_work_penalty", "1")),
        "assistance_penalty": float(get_professor_setting(conn, professor_user_id, "assistance_penalty", "1")),
    }


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


def penalty_summary(conn: sqlite3.Connection, user_id: int, scenario_id: int) -> Dict[str, Any]:
    rows = conn.execute(
        """SELECT event_type, COUNT(*) AS c, COALESCE(SUM(penalty_points), 0) AS points
        FROM student_support_events
        WHERE user_id=? AND scenario_id=?
        GROUP BY event_type""",
        (user_id, scenario_id),
    ).fetchall()
    by_type = {row["event_type"]: {"count": int(row["c"]), "points": float(row["points"])} for row in rows}
    assistance = by_type.get("assistance", {"count": 0, "points": 0.0})
    check_work = by_type.get("check_work", {"count": 0, "points": 0.0})
    total = assistance["points"] + check_work["points"]
    used_rows = conn.execute(
        """SELECT schedule_id, event_type FROM student_support_events
        WHERE user_id=? AND scenario_id=?""",
        (user_id, scenario_id),
    ).fetchall()
    return {
        "assistance_count": assistance["count"],
        "check_work_count": check_work["count"],
        "penalty_points": round(total, 2),
        "assistance_used": sorted(row["schedule_id"] for row in used_rows if row["event_type"] == "assistance"),
        "check_work_used": sorted(row["schedule_id"] for row in used_rows if row["event_type"] == "check_work"),
    }


def progress_grade(entries: Dict[str, Any], penalties: float) -> Dict[str, Any]:
    normalized = normalize_entries(entries)
    grading = grade_entries(normalized)
    raw_score = float(grading["score"])
    adjusted_score = max(0.0, raw_score - float(penalties))
    completed = 0
    for key in SOLUTION:
        raw = normalized.get(key)
        try:
            value = float(raw)
            if math.isfinite(value):
                completed += 1
        except (TypeError, ValueError):
            pass
    return {
        "raw_score": round(raw_score, 2),
        "penalty_points": round(float(penalties), 2),
        "adjusted_score": round(adjusted_score, 2),
        "completed_cells": completed,
        "possible_cells": len(SOLUTION),
    }


def _ascii_pdf_text(value: Any) -> str:
    text = str(value).replace("—", "-").replace("–", "-").replace("’", "'").replace("“", '"').replace("”", '"')
    return unicodedata.normalize("NFKD", text).encode("ascii", "replace").decode("ascii")


def _wrap_pdf_line(text: str, width: int = 92) -> list[str]:
    text = _ascii_pdf_text(text)
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def build_grade_pdf(student_name: str, submission: Dict[str, Any], grading: Dict[str, Any]) -> bytes:
    raw_score = float(submission.get("raw_score") if submission.get("raw_score") is not None else grading.get("raw_score", submission.get("score", 0)))
    penalty_points = float(submission.get("penalty_points") or grading.get("penalty_points", 0) or 0)
    final_score = float(submission.get("score", max(0, raw_score - penalty_points)))
    penalty_info = grading.get("penalty_summary", {})
    lines = [
        "Northbridge Components, Inc. - MBA Master Budget Simulation",
        "Student Grade Report",
        "",
        f"Student: {student_name}",
        f"Attempt: {submission.get('attempt_number')}",
        f"Submitted (UTC): {submission.get('submitted_at')}",
        "",
        f"Raw assignment score: {raw_score:.2f}%",
        f"Assistance uses: {int(penalty_info.get('assistance_count', 0))}",
        f"Check My Work uses: {int(penalty_info.get('check_work_count', 0))}",
        f"Total grade penalties: -{penalty_points:.2f} percentage point(s)",
        f"FINAL ADJUSTED GRADE: {final_score:.2f}%",
        "",
        "Section results:",
    ]
    for result in grading.get("schedule_results", {}).values():
        lines.append(
            f"{result.get('title')}: {float(result.get('score', 0)):.2f} / {float(result.get('weight', 0)):.2f} points; "
            f"{int(result.get('correct', 0))} of {int(result.get('possible_cells', 0))} cells correct"
        )
    lines += [
        "",
        "This PDF was generated by the course simulation for student upload to Canvas as grade evidence.",
        "The final adjusted grade includes the professor-configured penalties recorded for Assistance and Check My Work usage.",
    ]
    wrapped: list[str] = []
    for line in lines:
        wrapped.extend(_wrap_pdf_line(line))
    lines_per_page = 48
    pages = [wrapped[i:i+lines_per_page] for i in range(0, len(wrapped), lines_per_page)] or [[""]]

    objects: list[bytes] = []
    # 1 Catalog, 2 Pages, 3 Font; page/content objects follow.
    page_obj_ids = []
    content_obj_ids = []
    next_id = 4
    for _ in pages:
        page_obj_ids.append(next_id); content_obj_ids.append(next_id + 1); next_id += 2
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for page_id, content_id, page_lines in zip(page_obj_ids, content_obj_ids, pages):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii")
        )
        commands = ["BT", "/F1 10 Tf", "46 746 Td", "14 TL"]
        for i, line in enumerate(page_lines):
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if i:
                commands.append("T*")
            commands.append(f"({safe}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("ascii", "replace")
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj_id, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{obj_id} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(out)


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
                policy = get_student_policy(conn, session["user_id"])
                max_attempts = policy["max_attempts"]
                latest = conn.execute("SELECT submission_id, score, submitted_at FROM submissions WHERE user_id=? ORDER BY submission_id DESC LIMIT 1", (session["user_id"],)).fetchone()
            saved_entries = {r["cell_key"]: r["entered_value"] for r in rows}
            with db_connect() as conn:
                support = penalty_summary(conn, session["user_id"], session["scenario_id"])
            self._send_json({
                "entries": saved_entries,
                "attempts_used": attempts,
                "max_attempts": max_attempts,
                "latest": dict(latest) if latest else None,
                "support": support,
                "progress": progress_grade(saved_entries, support["penalty_points"]),
                "policy": policy,
            })
            return
        if path == "/api/student/results":
            session = self._require("student")
            if not session:
                return
            with db_connect() as conn:
                submission = conn.execute("SELECT * FROM submissions WHERE user_id=? ORDER BY submission_id DESC LIMIT 1", (session["user_id"],)).fetchone()
                policy = get_student_policy(conn, session["user_id"])
                allow_feedback = policy["allow_student_feedback"]
                if not submission:
                    self._send_json({"submission": None})
                    return
                details = json.loads(submission["grading_json"])
                if not allow_feedback:
                    details.pop("details", None)
            self._send_json({"submission": {**dict(submission), "grading": details}})
            return
        if path == "/api/student/grade.pdf":
            session = self._require("student")
            if not session:
                return
            with db_connect() as conn:
                row = conn.execute(
                    """SELECT s.*, u.display_name FROM submissions s
                    JOIN users u ON u.user_id=s.user_id
                    WHERE s.user_id=? ORDER BY s.submission_id DESC LIMIT 1""",
                    (session["user_id"],),
                ).fetchone()
                if not row:
                    self._send_json({"error": "Submit the assignment before downloading a grade PDF"}, 409)
                    return
                submission = dict(row)
                grading = json.loads(submission["grading_json"])
                conn.execute(
                    "INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'GRADE_PDF_DOWNLOAD', ?, ?)",
                    (session["user_id"], json.dumps({"submission_id": submission["submission_id"]}), now_iso()),
                )
                conn.commit()
            body = build_grade_pdf(submission["display_name"], submission, grading)
            ascii_name = _ascii_pdf_text(submission["display_name"])
            safe_name = "".join(ch if ch.isalnum() else "_" for ch in ascii_name).strip("_") or "student"
            filename = f"{safe_name}_Budget_Simulation_Grade_Attempt_{submission['attempt_number']}.pdf"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
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
                    WHERE sr.active=1 AND sr.professor_user_id=?
                    GROUP BY sr.student_id, u.user_id
                    ORDER BY sr.student_name""",
                    (session["user_id"],),
                ).fetchall()
                settings = {
                    r["setting_key"]: r["setting_value"]
                    for r in conn.execute(
                        "SELECT setting_key, setting_value FROM professor_settings WHERE professor_user_id=?",
                        (session["user_id"],),
                    )
                }
            self._send_json({"students": [dict(r) for r in rows], "settings": settings, "professor": session["display_name"]})
            return
        if path == "/api/professor/submissions":
            session = self._require("professor")
            if not session:
                return
            with db_connect() as conn:
                rows = conn.execute(
                    """SELECT s.submission_id, s.attempt_number, s.score, s.submitted_at,
                    u.username, u.display_name
                    FROM submissions s
                    JOIN users u ON u.user_id=s.user_id
                    JOIN student_roster sr ON sr.user_id=u.user_id
                    WHERE sr.professor_user_id=?
                    ORDER BY s.submitted_at DESC""",
                    (session["user_id"],),
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
                    JOIN student_roster sr ON sr.user_id=s.user_id
                    WHERE sr.professor_user_id=? AND NOT EXISTS (
                        SELECT 1 FROM dynamics_sync_log d
                        WHERE d.local_table='submissions'
                        AND d.local_record_id=CAST(s.submission_id AS TEXT)
                        AND d.sync_status='SUCCESS'
                    )""",
                    (session["user_id"],),
                ).fetchone()["c"]
                last_sync = conn.execute(
                    "SELECT sync_status, response_message, created_at FROM dynamics_sync_log WHERE user_id=? ORDER BY sync_id DESC LIMIT 1",
                    (session["user_id"],),
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
                    FROM submissions s
                    JOIN users u ON u.user_id=s.user_id
                    JOIN student_roster sr ON sr.user_id=u.user_id
                    WHERE sr.professor_user_id=?
                    ORDER BY u.display_name, s.attempt_number""",
                    (session["user_id"],),
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
                professor_username = PROFESSOR_LOGIN_MAP.get(login_name.lower())
                if professor_username:
                    user = conn.execute(
                        "SELECT * FROM users WHERE username=? AND role='professor' AND active=1",
                        (professor_username,),
                    ).fetchone()
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
                        self._send_json({
                            "error": "Invalid student name or password. If a password was previously created for this student, use the same five digits. The professor can clear the stored password from the Student Table when a first-time password must be created again."
                        }, 401)
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
        if path == "/api/student/progress":
            session = self._require("student")
            if not session:
                return
            entries = data.get("entries", {})
            if not isinstance(entries, dict):
                self._send_json({"error": "entries must be an object"}, 400)
                return
            with db_connect() as conn:
                support = penalty_summary(conn, session["user_id"], session["scenario_id"])
                policy = get_student_policy(conn, session["user_id"])
            self._send_json({"progress": progress_grade(entries, support["penalty_points"]), "support": support, "policy": policy})
            return
        if path == "/api/student/explanation":
            session = self._require("student")
            if not session:
                return
            schedule_id = str(data.get("schedule_id", "")).strip()
            guide = SUPPORT_GUIDE.get(schedule_id)
            if not guide:
                self._send_json({"error": "Unknown assignment section"}, 404)
                return
            schedule = next(s for s in SCHEDULES if s["id"] == schedule_id)
            with db_connect() as conn:
                conn.execute(
                    "INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'DETAILED_EXPLANATION', ?, ?)",
                    (session["user_id"], json.dumps({"schedule_id": schedule_id}), now_iso()),
                )
                conn.commit()
            self._send_json({"title": schedule["title"], "content": guide["explanation"], "penalty_points": 0})
            return
        if path == "/api/student/assistance":
            session = self._require("student")
            if not session:
                return
            schedule_id = str(data.get("schedule_id", "")).strip()
            guide = SUPPORT_GUIDE.get(schedule_id)
            if not guide:
                self._send_json({"error": "Unknown assignment section"}, 404)
                return
            schedule = next(s for s in SCHEDULES if s["id"] == schedule_id)
            with db_connect() as conn:
                policy = get_student_policy(conn, session["user_id"])
                penalty = float(policy["assistance_penalty"])
                cur = conn.execute(
                    """INSERT OR IGNORE INTO student_support_events
                    (user_id, scenario_id, schedule_id, event_type, penalty_points, created_at)
                    VALUES (?, ?, ?, 'assistance', ?, ?)""",
                    (session["user_id"], session["scenario_id"], schedule_id, penalty, now_iso()),
                )
                first_use = cur.rowcount > 0
                if first_use:
                    conn.execute(
                        "INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'ASSISTANCE_USED', ?, ?)",
                        (session["user_id"], json.dumps({"schedule_id": schedule_id, "penalty_points": penalty}), now_iso()),
                    )
                support = penalty_summary(conn, session["user_id"], session["scenario_id"])
                conn.commit()
            self._send_json({
                "title": schedule["title"], "content": guide["assistance"], "penalty_applied": penalty if first_use else 0,
                "already_used": not first_use, "support": support, "policy": policy,
            })
            return
        if path == "/api/student/check-work":
            session = self._require("student")
            if not session:
                return
            schedule_id = str(data.get("schedule_id", "")).strip()
            if schedule_id not in SCHEDULE_KEYS:
                self._send_json({"error": "Unknown assignment section"}, 404)
                return
            entries = data.get("entries", {})
            if not isinstance(entries, dict):
                self._send_json({"error": "entries must be an object"}, 400)
                return
            with db_connect() as conn:
                policy = get_student_policy(conn, session["user_id"])
                if not policy["check_work_enabled"]:
                    self._send_json({"error": "Check My Work is disabled for this class section"}, 403)
                    return
                existing = conn.execute(
                    """SELECT 1 FROM student_support_events
                    WHERE user_id=? AND scenario_id=? AND schedule_id=? AND event_type='check_work'""",
                    (session["user_id"], session["scenario_id"], schedule_id),
                ).fetchone()
                if existing:
                    self._send_json({"error": "Check My Work has already been used for this section"}, 409)
                    return
                penalty = float(policy["check_work_penalty"])
                conn.execute(
                    """INSERT INTO student_support_events
                    (user_id, scenario_id, schedule_id, event_type, penalty_points, created_at)
                    VALUES (?, ?, ?, 'check_work', ?, ?)""",
                    (session["user_id"], session["scenario_id"], schedule_id, penalty, now_iso()),
                )
                grading = grade_entries(entries)
                schedule_result = grading["schedule_results"][schedule_id]
                cell_feedback = {
                    key: {"actual": grading["details"][key]["actual"], "correct": grading["details"][key]["correct"]}
                    for key in SCHEDULE_KEYS[schedule_id]
                }
                conn.execute(
                    "INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'CHECK_WORK_USED', ?, ?)",
                    (session["user_id"], json.dumps({"schedule_id": schedule_id, "penalty_points": penalty, "correct": schedule_result["correct"], "possible_cells": schedule_result["possible_cells"]}), now_iso()),
                )
                support = penalty_summary(conn, session["user_id"], session["scenario_id"])
                conn.commit()
            self._send_json({
                "schedule_id": schedule_id, "result": schedule_result, "details": cell_feedback,
                "penalty_applied": penalty, "support": support, "policy": policy,
                "progress": progress_grade(entries, support["penalty_points"]),
            })
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
                policy = get_student_policy(conn, session["user_id"])
                max_attempts = policy["max_attempts"]
                if attempts >= max_attempts:
                    self._send_json({"error": "Maximum number of attempts reached"}, 409)
                    return
                grading = grade_entries(entries)
                support = penalty_summary(conn, session["user_id"], session["scenario_id"])
                raw_score = float(grading["score"])
                penalty_points = float(support["penalty_points"])
                adjusted_score = round(max(0.0, raw_score - penalty_points), 2)
                grading["raw_score"] = round(raw_score, 2)
                grading["penalty_points"] = round(penalty_points, 2)
                grading["penalty_summary"] = support
                grading["score"] = adjusted_score
                attempt_no = attempts + 1
                cur = conn.execute(
                    """INSERT INTO submissions
                    (user_id, scenario_id, attempt_number, score, raw_score, penalty_points, entries_json, grading_json, submitted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (session["user_id"], session["scenario_id"], attempt_no, adjusted_score, raw_score, penalty_points, json.dumps(entries), json.dumps(grading), now_iso()),
                )
                submission_id = cur.lastrowid
                for sid, result in grading["schedule_results"].items():
                    conn.execute(
                        """INSERT INTO submission_schedule_scores
                        (submission_id, schedule_id, schedule_title, earned_points, possible_points, correct_cells, possible_cells)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (submission_id, sid, result["title"], result["score"], result["weight"], result["correct"], result["possible_cells"]),
                    )
                conn.execute("INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'SUBMIT', ?, ?)", (session["user_id"], json.dumps({"attempt": attempt_no, "score": grading["score"], "raw_score": grading.get("raw_score"), "penalty_points": grading.get("penalty_points", 0)}), now_iso()))
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
                    duplicate = conn.execute(
                        """SELECT sr.professor_user_id, u.display_name AS professor_name
                        FROM student_roster sr
                        JOIN users u ON u.user_id=sr.professor_user_id
                        WHERE lower(trim(sr.student_name))=lower(trim(?))""",
                        (display_name,),
                    ).fetchone()
                    if duplicate:
                        owner = duplicate["professor_name"]
                        self._send_json({"error": f"That student name is already assigned to {owner}. Student names must be unique across professor rosters so the existing student login method remains unambiguous."}, 409)
                        return
                    ensure_roster_student(conn, session["scenario_id"], session["user_id"], display_name)
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
                owned = conn.execute(
                    "SELECT 1 FROM student_roster WHERE user_id=? AND professor_user_id=? AND active=1",
                    (user_id, session["user_id"]),
                ).fetchone()
                if not owned:
                    self._send_json({"error": "Student is not in this professor's Student Table"}, 404)
                    return
                conn.execute("DELETE FROM submission_schedule_scores WHERE submission_id IN (SELECT submission_id FROM submissions WHERE user_id=?)", (user_id,))
                conn.execute("DELETE FROM submissions WHERE user_id=?", (user_id,))
                conn.execute("DELETE FROM student_entries WHERE user_id=?", (user_id,))
                conn.execute("DELETE FROM student_support_events WHERE user_id=?", (user_id,))
                conn.execute("INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'PROFESSOR_RESET', ?, ?)", (session["user_id"], json.dumps({"student_user_id": user_id}), now_iso()))
                conn.commit()
            self._send_json({"ok": True})
            return
        if path == "/api/professor/reset-password":
            session = self._require("professor")
            if not session:
                return
            try:
                user_id = int(data.get("user_id"))
            except (TypeError, ValueError):
                self._send_json({"error": "Valid user_id required"}, 400)
                return
            with db_connect() as conn:
                roster = conn.execute(
                    "SELECT student_id, student_name FROM student_roster WHERE user_id=? AND professor_user_id=? AND active=1",
                    (user_id, session["user_id"]),
                ).fetchone()
                if not roster:
                    self._send_json({"error": "Student was not found in the active Student Table"}, 404)
                    return
                conn.execute(
                    "UPDATE student_roster SET password=NULL, password_created_at=NULL WHERE student_id=?",
                    (roster["student_id"],),
                )
                conn.execute(
                    "INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'PROFESSOR_RESET_PASSWORD', ?, ?)",
                    (session["user_id"], json.dumps({"student_user_id": user_id, "student_name": roster["student_name"]}), now_iso()),
                )
                conn.commit()
            self._send_json({"ok": True})
            return
        if path == "/api/professor/clear-student-table":
            session = self._require("professor")
            if not session:
                return
            confirmation = str(data.get("confirmation", "")).strip()
            if confirmation != "CLEAR STUDENT TABLE":
                self._send_json({"error": "Type CLEAR STUDENT TABLE exactly to confirm the end-of-semester clear"}, 400)
                return
            deleted_user_ids = []
            with db_connect() as conn:
                rows = conn.execute(
                    "SELECT user_id FROM student_roster WHERE professor_user_id=?",
                    (session["user_id"],),
                ).fetchall()
                deleted_user_ids = [int(row["user_id"]) for row in rows]
                students_removed = len(deleted_user_ids)
                # Delete only students owned by the currently authenticated professor.
                # Cascades remove that professor's roster rows, drafts, submissions,
                # schedule scores, and support events without affecting other rosters.
                if deleted_user_ids:
                    placeholders = ",".join("?" for _ in deleted_user_ids)
                    conn.execute(f"DELETE FROM users WHERE user_id IN ({placeholders}) AND role='student'", deleted_user_ids)
                conn.execute(
                    """INSERT INTO student_roster_clear_log
                    (professor_user_id, students_removed, cleared_at)
                    VALUES (?, ?, ?)""",
                    (session["user_id"], students_removed, now_iso()),
                )
                conn.execute(
                    "INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'PROFESSOR_CLEAR_STUDENT_TABLE', ?, ?)",
                    (session["user_id"], json.dumps({"students_removed": students_removed}), now_iso()),
                )
                conn.commit()
            if deleted_user_ids:
                deleted = set(deleted_user_ids)
                with SESSIONS_LOCK:
                    for token, existing_session in list(SESSIONS.items()):
                        if existing_session.get("role") == "student" and existing_session.get("user_id") in deleted:
                            SESSIONS.pop(token, None)
            self._send_json({"ok": True, "students_removed": len(deleted_user_ids)})
            return
        if path == "/api/professor/settings":
            session = self._require("professor")
            if not session:
                return
            allowed = {"max_attempts", "passing_score", "allow_student_feedback", "check_work_enabled", "check_work_penalty", "assistance_penalty"}
            # Validate settings before storing them for this professor only.
            try:
                max_attempts = int(data.get("max_attempts", 3))
                passing_score = float(data.get("passing_score", 80))
                check_work_penalty = float(data.get("check_work_penalty", 1))
                assistance_penalty = float(data.get("assistance_penalty", 1))
            except (TypeError, ValueError):
                self._send_json({"error": "Assignment settings contain an invalid number"}, 400)
                return
            if not 1 <= max_attempts <= 10:
                self._send_json({"error": "Maximum attempts must be between 1 and 10"}, 400)
                return
            if not 0 <= passing_score <= 100 or not 0 <= check_work_penalty <= 100 or not 0 <= assistance_penalty <= 100:
                self._send_json({"error": "Scores and penalty points must be between 0 and 100"}, 400)
                return
            normalized = {
                "max_attempts": str(max_attempts),
                "passing_score": str(passing_score),
                "allow_student_feedback": "1" if str(data.get("allow_student_feedback", "1")) in {"1", "True", "true"} or data.get("allow_student_feedback") is True else "0",
                "check_work_enabled": "1" if str(data.get("check_work_enabled", "1")) in {"1", "True", "true"} or data.get("check_work_enabled") is True else "0",
                "check_work_penalty": str(check_work_penalty),
                "assistance_penalty": str(assistance_penalty),
            }
            with db_connect() as conn:
                for key, value in normalized.items():
                    if key in allowed:
                        conn.execute(
                            """INSERT INTO professor_settings(professor_user_id, setting_key, setting_value)
                            VALUES (?, ?, ?)
                            ON CONFLICT(professor_user_id, setting_key)
                            DO UPDATE SET setting_value=excluded.setting_value""",
                            (session["user_id"], key, value),
                        )
                conn.execute(
                    "INSERT INTO audit_log(user_id, action, details_json, created_at) VALUES (?, 'PROFESSOR_SETTINGS_UPDATE', ?, ?)",
                    (session["user_id"], json.dumps(normalized), now_iso()),
                )
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
                    FROM submissions s
                    JOIN users u ON u.user_id=s.user_id
                    JOIN student_roster sr ON sr.user_id=u.user_id
                    WHERE sr.professor_user_id=? AND NOT EXISTS (
                        SELECT 1 FROM dynamics_sync_log d
                        WHERE d.local_table='submissions'
                        AND d.local_record_id=CAST(s.submission_id AS TEXT)
                        AND d.sync_status='SUCCESS'
                    )
                    ORDER BY s.submission_id""",
                    (session["user_id"],),
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
    print("Professor login names: Professor, Professor 1, Professor 2")
    print(f"Initial student roster contains {len(STUDENT_ROSTER_NAMES)} students; first login creates a five-digit numerical password")
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
