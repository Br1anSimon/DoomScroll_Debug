# DoomScroll Diary

DoomScroll Diary is a small Flask web app for tracking social media habits. Users can create an account, log daily screen time, set personal goals, maintain a login streak, write journal entries, and rate how they felt for each journal entry.

## Features

- **Account login and registration:** Users can create an account and keep their entries tied to their session.
- **Goals and streaks:** Users can add goals, mark them complete, and see their current login streak.
- **Screen time log:** Users can record time spent on common apps or a custom app.
- **Trends:** The app summarizes the last 7 days of logged screen time and shows app-by-app totals.
- **Diary:** Users can save journal entries and select a 1-5 feeling rating with emojis from upset to happy.
- **Settings:** Users can change their password from the settings modal.

## Tech Stack

- **Backend:** Python, Flask, Flask-CORS, SQLite.
- **Frontend:** HTML, CSS, and inline browser JavaScript served by Flask.
- **Database:** `backend/doomscroll.db` is created locally when the Flask app starts.
- **Container:** The Dockerfile builds a Python image and runs the Flask backend.

## Project Structure

```text
backend/
  backend.py          Flask app, API routes, database setup, static file serving
  README.md           Backend-specific setup, database, and API documentation
  requirements.txt    Python dependencies
  .gitignore          Ignores the local SQLite database
frontend/
  html/index.html     Login and registration page
  html/home.html      Main authenticated app UI
  css/styles.css      App styling
  js/app.js           Reserved for future frontend JavaScript
Dockerfile            Container build for the Flask app
readme.md             Project documentation
```

## Local Setup

1. Clone the repository.

   ```powershell
   git clone https://github.com/Br1anSimon/DoomScroll_Debug.git
   cd DoomScroll_Debug
   ```

2. Install backend dependencies.

   ```powershell
   pip install -r backend/requirements.txt
   ```

3. Run the Flask app.

   ```powershell
   python backend/backend.py
   ```

4. Open the app in your browser.

   ```text
   http://localhost:8000
   ```

For backend details, see `backend/README.md`.

## Docker

Build and run the container:

```powershell
docker build -t doomscroll-diary .
docker run --rm -p 8000:8000 doomscroll-diary
```

Then open:

```text
http://localhost:8000
```

## API Summary

- `POST /api/register` creates an account and starts a session.
- `POST /api/login` starts a session.
- `POST /api/logout` clears the session.
- `GET /api/me` returns the current logged-in user.
- `GET /api/streak` returns the user's login streak.
- `GET /api/goals`, `POST /api/goals`, `PATCH /api/goals/<id>`, and `DELETE /api/goals/<id>` manage goals.
- `GET /api/screentime`, `POST /api/screentime`, and `DELETE /api/screentime/<id>` manage screen time logs.
- `GET /api/trends` returns 7-day screen time summaries.
- `GET /api/journal`, `POST /api/journal`, and `DELETE /api/journal/<id>` manage diary entries and feeling ratings.
- `POST /api/change-password` updates the logged-in user's password.

## Local Files

The SQLite database is local development state and should not be committed:

```text
backend/doomscroll.db
```

It is ignored by `backend/.gitignore`.

## Team Members and Contributions

- Jacob Klinedinst: Database schema, backend setup, and UI/database integration.
- Brian Simon: Frontend and UI features, deployment collaboration.
- Cole Caron: Backend/database communication and UI integration.
- Lena: Docker setup, deployment, README, and frontend implementation.
- Shin: Settings tab and change-password feature.
- James Casella: Project feature implementation and support.
