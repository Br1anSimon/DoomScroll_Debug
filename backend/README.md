# Backend Documentation

The active backend is `backend.py`. It is a Flask application that serves both the JSON API and the frontend pages from `frontend/html`.

`server.py` is a legacy FastAPI prototype and is not used by the current app.

## Running Locally

Install dependencies from the repository root:

```powershell
pip install -r backend/requirements.txt
```

Start the backend:

```powershell
python backend/backend.py
```

Open the app at:

```text
http://localhost:8000
```

## Database

The app uses SQLite at:

```text
backend/doomscroll.db
```

`init_db()` creates the database tables when the app starts. It also runs a small migration that adds `feeling_rating` to `journal_entries` if an older local database is missing that column.

The database is local runtime state and should not be committed. It is ignored by `backend/.gitignore`.

## Main Tables

- `users`: account information, login names, hashed passwords, and optional email.
- `journal_entries`: diary entries with optional title, content, timestamps, and a 1-5 `feeling_rating`.
- `time_logs`: daily screen time logs by activity/app and duration.
- `goals`: user-created goals and completion state.
- `login_days`: one row per user per login date for streak tracking.

## Auth and Sessions

The app uses Flask sessions. Login and registration store `user_id` and `username` in the session cookie. Routes that need an authenticated user use the `login_required` decorator.

Passwords are currently hashed with SHA-256 in `hash_password()`.

## API Routes

### Auth

- `POST /api/register`: creates a user and starts a session.
- `POST /api/login`: verifies credentials and starts a session.
- `POST /api/logout`: clears the current session.
- `GET /api/me`: returns the current logged-in user.

### Goals

- `GET /api/goals`: returns the current user's goals.
- `POST /api/goals`: creates a goal.
- `PATCH /api/goals/<goal_id>`: updates goal completion.
- `DELETE /api/goals/<goal_id>`: deletes a goal.

### Screen Time

- `GET /api/screentime`: returns today's screen time logs.
- `POST /api/screentime`: creates a log entry.
- `DELETE /api/screentime/<log_id>`: deletes a log entry.
- `GET /api/trends`: returns 7-day totals and app summaries.

### Journal

- `GET /api/journal`: returns diary entries newest first.
- `POST /api/journal`: creates a diary entry with `content` and `feeling_rating`.
- `DELETE /api/journal/<entry_id>`: deletes a diary entry.

### Account Settings

- `POST /api/change-password`: changes the logged-in user's password.

## Static Pages

- `GET /`: serves `frontend/html/index.html`.
- `GET /home`: serves `frontend/html/home.html`.

## Notes for Future Backend Work

- Keep new database columns backward compatible by adding small migrations in `init_db()`.
- Keep authenticated SQL queries scoped by `current_user_id()` so users can only access their own data.
- If the backend port changes, update `backend.py`, `Dockerfile`, `readme.md`, and this file together.
