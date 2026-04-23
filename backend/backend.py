
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime, date, timedelta
from functools import wraps
 
from flask import Flask, request, jsonify, session, g
from flask_cors import CORS
 
# ── App setup ──────────────────────────────────────────────────────────────────
 
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "../frontend"), static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
CORS(app, supports_credentials=True)
 
DB_PATH = os.path.join(os.path.dirname(__file__), "doomscroll.db")
 
# ── Database helpers ───────────────────────────────────────────────────────────
 
def get_db():
    """Return a per-request SQLite connection stored on Flask's g object."""
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row          # rows behave like dicts
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db
 
@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
 
def init_db():
    """Create tables from schema.sql (plus a goals table the schema doesn't have)."""
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
 
    # Original schema tables
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
 
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
 
        CREATE TABLE IF NOT EXISTS time_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity TEXT NOT NULL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            duration_minutes INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
 
        CREATE INDEX IF NOT EXISTS idx_journal_entries_user_id ON journal_entries(user_id);
        CREATE INDEX IF NOT EXISTS idx_time_logs_user_id      ON time_logs(user_id);
        CREATE INDEX IF NOT EXISTS idx_time_logs_created_at   ON time_logs(created_at);
 
        -- Goals table (not in original schema but used by the frontend)
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
 
        -- Login-day tracker for streak calculation
        CREATE TABLE IF NOT EXISTS login_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            login_date DATE NOT NULL,
            UNIQUE(user_id, login_date),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    db.commit()
    db.close()
 
# ── Password hashing ───────────────────────────────────────────────────────────
 
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
 
# ── Auth decorator ─────────────────────────────────────────────────────────────
 
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not logged in"}), 401
        return f(*args, **kwargs)
    return decorated
 
def current_user_id() -> int:
    return session["user_id"]
 
# ── Auth endpoints ─────────────────────────────────────────────────────────────
 
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    name     = (data.get("name")     or "").strip()
    password = (data.get("password") or "").strip()
    email    = (data.get("email")    or "").strip() or None
 
    if not username or not name or not password:
        return jsonify({"error": "username, name, and password are required"}), 400
 
    db = get_db()
    try:
        db.execute(
            "INSERT INTO users (username, name, password, email) VALUES (?, ?, ?, ?)",
            (username, name, hash_password(password), email)
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username or email already taken"}), 409
 
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    _record_login(db, user["id"])
    return jsonify({"id": user["id"], "username": user["username"], "name": user["name"]}), 201
 
 
@app.route("/api/login", methods=["POST"])
def login():
    data     = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
 
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
 
    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
 
    if not user or user["password"] != hash_password(password):
        return jsonify({"error": "Invalid username or password"}), 401
 
    session["user_id"]  = user["id"]
    session["username"] = user["username"]
    _record_login(db, user["id"])
    return jsonify({"id": user["id"], "username": user["username"], "name": user["name"]})
 
 
@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})
 
 
@app.route("/api/me", methods=["GET"])
@login_required
def me():
    db   = get_db()
    user = db.execute("SELECT id, username, name, email FROM users WHERE id = ?",
                      (current_user_id(),)).fetchone()
    return jsonify(dict(user))
 
# ── Streak helper ──────────────────────────────────────────────────────────────
 
def _record_login(db, user_id: int):
    today = date.today().isoformat()
    db.execute(
        "INSERT OR IGNORE INTO login_days (user_id, login_date) VALUES (?, ?)",
        (user_id, today)
    )
    db.commit()
 
 
@app.route("/api/streak", methods=["GET"])
@login_required
def streak():
    db   = get_db()
    rows = db.execute(
        "SELECT login_date FROM login_days WHERE user_id = ? ORDER BY login_date DESC",
        (current_user_id(),)
    ).fetchall()
 
    if not rows:
        return jsonify({"streak": 0})
 
    streak_count = 0
    check = date.today()
    for row in rows:
        d = date.fromisoformat(row["login_date"])
        if d == check:
            streak_count += 1
            check -= timedelta(days=1)
        elif d < check:
            break   # gap found
 
    return jsonify({"streak": streak_count})
 
# ── Goals ──────────────────────────────────────────────────────────────────────
 
@app.route("/api/goals", methods=["GET"])
@login_required
def get_goals():
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM goals WHERE user_id = ? ORDER BY created_at ASC",
        (current_user_id(),)
    ).fetchall()
    return jsonify([dict(r) for r in rows])
 
 
@app.route("/api/goals", methods=["POST"])
@login_required
def add_goal():
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Goal text required"}), 400
 
    db = get_db()
    cur = db.execute(
        "INSERT INTO goals (user_id, text) VALUES (?, ?)",
        (current_user_id(), text)
    )
    db.commit()
    row = db.execute("SELECT * FROM goals WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201
 
 
@app.route("/api/goals/<int:goal_id>", methods=["PATCH"])
@login_required
def update_goal(goal_id):
    data      = request.get_json(force=True)
    completed = 1 if data.get("completed") else 0
 
    db  = get_db()
    cur = db.execute(
        "UPDATE goals SET completed = ? WHERE id = ? AND user_id = ?",
        (completed, goal_id, current_user_id())
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Goal not found"}), 404
    row = db.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    return jsonify(dict(row))
 
 
@app.route("/api/goals/<int:goal_id>", methods=["DELETE"])
@login_required
def delete_goal(goal_id):
    db  = get_db()
    cur = db.execute(
        "DELETE FROM goals WHERE id = ? AND user_id = ?",
        (goal_id, current_user_id())
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Goal not found"}), 404
    return jsonify({"deleted": goal_id})
 
# ── Screen time (time_logs) ────────────────────────────────────────────────────
 
@app.route("/api/screentime", methods=["GET"])
@login_required
def get_screentime():
    """Return today's time logs for the current user."""
    db      = get_db()
    today   = date.today().isoformat()
    rows    = db.execute(
        """SELECT * FROM time_logs
           WHERE user_id = ? AND DATE(created_at) = ?
           ORDER BY created_at DESC""",
        (current_user_id(), today)
    ).fetchall()
    return jsonify([dict(r) for r in rows])
 
 
@app.route("/api/screentime", methods=["POST"])
@login_required
def add_screentime():
    """
    Expected JSON:
      { "activity": "TikTok", "duration_minutes": 45 }
    """
    data             = request.get_json(force=True)
    activity         = (data.get("activity") or "").strip()
    duration_minutes = int(data.get("duration_minutes") or 0)
 
    if not activity or duration_minutes <= 0:
        return jsonify({"error": "activity and duration_minutes (> 0) required"}), 400
 
    now = datetime.utcnow().isoformat()
    db  = get_db()
    cur = db.execute(
        """INSERT INTO time_logs (user_id, activity, start_time, duration_minutes)
           VALUES (?, ?, ?, ?)""",
        (current_user_id(), activity, now, duration_minutes)
    )
    db.commit()
    row = db.execute("SELECT * FROM time_logs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201
 
 
@app.route("/api/screentime/<int:log_id>", methods=["DELETE"])
@login_required
def delete_screentime(log_id):
    db  = get_db()
    cur = db.execute(
        "DELETE FROM time_logs WHERE id = ? AND user_id = ?",
        (log_id, current_user_id())
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Log entry not found"}), 404
    return jsonify({"deleted": log_id})
 
# ── Trends ────────────────────────────────────────────────────────────────────
 
@app.route("/api/trends", methods=["GET"])
@login_required
def trends():
    """
    Returns:
      - daily_totals: [{date, total_minutes}] for last 7 days
      - by_app: [{activity, total_minutes}] for last 7 days, sorted desc
      - daily_average: average minutes/day over last 7 days
      - worst_day: {date, total_minutes}
      - best_day: {date, total_minutes}
    """
    db = get_db()
    uid = current_user_id()
 
    # Last 7 days including today
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
 
    # Daily totals
    rows = db.execute("""
        SELECT DATE(created_at) as day, SUM(duration_minutes) as total
        FROM time_logs
        WHERE user_id = ? AND DATE(created_at) >= ?
        GROUP BY day
    """, (uid, days[0])).fetchall()
    day_map = {r["day"]: r["total"] for r in rows}
    daily_totals = [{"date": d, "total_minutes": day_map.get(d, 0)} for d in days]
 
    # By app (last 7 days)
    app_rows = db.execute("""
        SELECT activity, SUM(duration_minutes) as total
        FROM time_logs
        WHERE user_id = ? AND DATE(created_at) >= ?
        GROUP BY activity
        ORDER BY total DESC
    """, (uid, days[0])).fetchall()
    by_app = [{"activity": r["activity"], "total_minutes": r["total"]} for r in app_rows]
 
    totals = [d["total_minutes"] for d in daily_totals]
    non_zero = [t for t in totals if t > 0]
    daily_average = round(sum(non_zero) / len(non_zero)) if non_zero else 0
 
    worst = max(daily_totals, key=lambda d: d["total_minutes"]) if non_zero else None
    best  = min([d for d in daily_totals if d["total_minutes"] > 0], key=lambda d: d["total_minutes"]) if non_zero else None
 
    return jsonify({
        "daily_totals": daily_totals,
        "by_app": by_app,
        "daily_average": daily_average,
        "worst_day": worst,
        "best_day": best,
    })
 
# ── Journal (journal_entries) ──────────────────────────────────────────────────
 
@app.route("/api/journal", methods=["GET"])
@login_required
def get_journal():
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM journal_entries WHERE user_id = ? ORDER BY created_at DESC",
        (current_user_id(),)
    ).fetchall()
    return jsonify([dict(r) for r in rows])
 
 
@app.route("/api/journal", methods=["POST"])
@login_required
def add_journal():
    """
    Expected JSON:
      { "content": "Dear diary...", "title": "optional title" }
    """
    data    = request.get_json(force=True)
    content = (data.get("content") or "").strip()
    title   = (data.get("title")   or "").strip() or None
 
    if not content:
        return jsonify({"error": "content required"}), 400
 
    db  = get_db()
    cur = db.execute(
        "INSERT INTO journal_entries (user_id, title, content) VALUES (?, ?, ?)",
        (current_user_id(), title, content)
    )
    db.commit()
    row = db.execute("SELECT * FROM journal_entries WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201
 
 
@app.route("/api/journal/<int:entry_id>", methods=["DELETE"])
@login_required
def delete_journal(entry_id):
    db  = get_db()
    cur = db.execute(
        "DELETE FROM journal_entries WHERE id = ? AND user_id = ?",
        (entry_id, current_user_id())
    )
    db.commit()
    if cur.rowcount == 0:
        return jsonify({"error": "Entry not found"}), 404
    return jsonify({"deleted": entry_id})
 
# ── Entry point ────────────────────────────────────────────────────────────────
 
@app.route("/")
def root():
    return app.send_static_file("html/index.html")
 
@app.route("/home")
def home():
    return app.send_static_file("html/home.html")
 
if __name__ == "__main__":
    init_db()
    print("✦ DoomScroll Diary backend running at http://localhost:5000")
    app.run(debug=True, port=5000)