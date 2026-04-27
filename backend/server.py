"""Legacy FastAPI prototype.

The active application for this project is `backend.py`, which serves the
Flask API and frontend pages. Keep this file only as reference unless the team
decides to migrate back to FastAPI.
"""

import os
import sqlite3
from datetime import datetime, timedelta

import bcrypt
from fastapi import FastAPI, HTTPException, Response, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────
JWT_SECRET = os.environ["JWT_SECRET"]   # export JWT_SECRET=some-long-random-string
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7
DB_PATH = "diary.db"

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],  # your frontend origin
    allow_credentials=True,                   # needed for cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB helper ─────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # lets you access columns by name
    try:
        yield conn
    finally:
        conn.close()

# ── Schemas ───────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    name: str
    password: str
    email: str | None = None

# ── JWT helpers ───────────────────────────────────────────────────────────────
def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

# ── Auth dependency ───────────────────────────────────────────────────────────
def require_auth(request: Request) -> dict:
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_token(token)

# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/api/login")
def login(body: LoginRequest, response: Response, db: sqlite3.Connection = Depends(get_db)):
    user = db.execute(
        "SELECT * FROM users WHERE username = ?", (body.username,)
    ).fetchone()

    # same error for bad username OR bad password — don't leak which one
    invalid = HTTPException(status_code=401, detail="Invalid credentials")

    if not user:
        raise invalid

    password_matches = bcrypt.checkpw(
        body.password.encode("utf-8"),
        user["password"].encode("utf-8")
    )
    if not password_matches:
        raise invalid

    token = create_token(user["id"], user["username"])

    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,                        # JS cannot read this
        secure=True,                          # HTTPS only — set False for local dev
        samesite="strict",
        max_age=JWT_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return {"success": True, "name": user["name"]}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("auth_token")
    return {"success": True}


@app.get("/api/me")
def me(current_user: dict = Depends(require_auth)):
    return {"userId": current_user["sub"], "username": current_user["username"]}


@app.post("/api/register")
def register(body: RegisterRequest, db: sqlite3.Connection = Depends(get_db)):
    # check if username already taken
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (body.username,)
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")

    hashed = bcrypt.hashpw(body.password.encode("utf-8"), bcrypt.gensalt(rounds=12))

    db.execute(
        "INSERT INTO users (username, name, password, email) VALUES (?, ?, ?, ?)",
        (body.username, body.name, hashed.decode("utf-8"), body.email),
    )
    db.commit()
    return {"success": True}
