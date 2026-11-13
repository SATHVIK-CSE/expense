from datetime import date, datetime, timezone
import base64
import hashlib
import hmac
import os
import re
from typing import Literal
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from js import Object, Uint8Array, crypto
from pyodide.ffi import to_js as _to_js
from workers import asgi


def to_js(value):
    return _to_js(value, dict_converter=Object.fromEntries)

app = FastAPI(title="KS Projects Expense Tracker")
SESSION_COOKIE = "xp_session"
SESSION_SECONDS = 60 * 60 * 24 * 14


class ExpenseIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=100000000)
    category: Literal["Food", "Transport", "Shopping", "Bills", "Health", "Entertainment", "Other"]
    expense_date: date
    note: str = Field(default="", max_length=300)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)


async def d1(request: Request):
    return request.scope["env"].DB


def secret_for(request: Request) -> str:
    secret = getattr(request.scope["env"], "AUTH_SECRET", None)
    if not secret:
        raise HTTPException(status_code=503, detail="Account sign-in is not configured yet.")
    return str(secret)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def make_session(user_id: int, secret: str) -> str:
    expires = int(datetime.now(timezone.utc).timestamp()) + SESSION_SECONDS
    payload = b64url(f"{user_id}:{expires}".encode("utf-8"))
    signature = b64url(hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_session(token: str | None, secret: str) -> int | None:
    if not token or "." not in token:
        return None
    payload, signature = token.split(".", 1)
    expected = b64url(hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8")
        user_id_text, expires_text = decoded.split(":", 1)
        if int(expires_text) <= int(datetime.now(timezone.utc).timestamp()):
            return None
        user_id = int(user_id_text)
        return user_id if user_id > 0 else None
    except (ValueError, UnicodeDecodeError):
        return None


async def authenticated_user(request: Request):
    user_id = read_session(request.cookies.get(SESSION_COOKIE), secret_for(request))
    if user_id is None:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    db = await d1(request)
    result = await db.prepare("SELECT id, username FROM users WHERE id = ?").bind(user_id).run()
    if not result.results:
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    return result.results[0]


async def password_hash(password: str, salt: bytes) -> str:
    """Derive a PBKDF2-SHA256 password hash with Workers' Web Crypto API."""
    key = await crypto.subtle.importKey(
        "raw",
        Uint8Array.new(password.encode("utf-8")),
        "PBKDF2",
        False,
        to_js(["deriveBits"]),
    )
    derived = await crypto.subtle.deriveBits(
        to_js({
            "name": "PBKDF2",
            "salt": Uint8Array.new(salt),
            "iterations": 100000,
            "hash": "SHA-256",
        }),
        key,
        256,
    )
    return Uint8Array.new(derived).to_bytes().hex()


async def issue_session(request: Request, user: dict):
    response = JSONResponse({"username": user["username"]})
    response.set_cookie(
        SESSION_COOKIE,
        make_session(int(user["id"]), secret_for(request)),
        max_age=SESSION_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response


@app.post("/api/auth/register", status_code=201)
async def register(credentials: Credentials, request: Request):
    username = credentials.username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        raise HTTPException(status_code=422, detail="Use 3–32 letters, numbers, dots, dashes, or underscores.")
    db = await d1(request)
    existing = await db.prepare("SELECT id FROM users WHERE username_key = ?").bind(username.lower()).run()
    if existing.results:
        raise HTTPException(status_code=409, detail="That username is already in use.")
    salt = os.urandom(16)
    digest = await password_hash(credentials.password, salt)
    await db.prepare(
        "INSERT INTO users (username, username_key, password_salt, password_hash) VALUES (?, ?, ?, ?)"
    ).bind(username, username.lower(), salt.hex(), digest).run()
    result = await db.prepare("SELECT id, username FROM users WHERE username_key = ?").bind(username.lower()).run()
    return await issue_session(request, result.results[0])


@app.post("/api/auth/login")
async def login(credentials: Credentials, request: Request):
    username = credentials.username.strip().lower()
    db = await d1(request)
    result = await db.prepare(
        "SELECT id, username, password_salt, password_hash FROM users WHERE username_key = ?"
    ).bind(username).run()
    if not result.results:
        raise HTTPException(status_code=401, detail="Username or password is incorrect.")
    user = result.results[0]
    try:
        salt = bytes.fromhex(user["password_salt"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=500, detail="Could not verify this account.")
    digest = await password_hash(credentials.password, salt)
    if not hmac.compare_digest(digest, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Username or password is incorrect.")
    return await issue_session(request, user)


@app.get("/api/auth/me")
async def me(request: Request):
    user = await authenticated_user(request)
    return {"username": user["username"]}


@app.post("/api/auth/logout")
async def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=True, samesite="lax")
    return response


@app.get("/api/expenses")
async def list_expenses(
    request: Request,
    search: str = Query(default="", max_length=100),
    category: str = "All",
):
    user = await authenticated_user(request)
    db = await d1(request)
    sql = "SELECT id, title, amount, category, expense_date, note FROM expenses WHERE user_id = ?"
    values = [int(user["id"])]
    if search.strip():
        sql += " AND (title LIKE ? OR note LIKE ?)"
        term = f"%{search.strip()}%"
        values.extend([term, term])
    if category != "All":
        sql += " AND category = ?"
        values.append(category)
    sql += " ORDER BY expense_date DESC, id DESC"
    result = await db.prepare(sql).bind(*values).run()
    return result.results


@app.post("/api/expenses", status_code=201)
async def add_expense(expense: ExpenseIn, request: Request):
    user = await authenticated_user(request)
    db = await d1(request)
    await db.prepare(
        "INSERT INTO expenses (user_id, title, amount, category, expense_date, note) VALUES (?, ?, ?, ?, ?, ?)"
    ).bind(
        int(user["id"]), expense.title.strip(), expense.amount, expense.category,
        expense.expense_date.isoformat(), expense.note.strip()
    ).run()
    result = await db.prepare(
        "SELECT id, title, amount, category, expense_date, note FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1"
    ).bind(int(user["id"])).run()
    return result.results[0]


@app.delete("/api/expenses/{expense_id}", status_code=204)
async def delete_expense(expense_id: int, request: Request):
    user = await authenticated_user(request)
    db = await d1(request)
    result = await db.prepare("DELETE FROM expenses WHERE id = ? AND user_id = ?").bind(
        expense_id, int(user["id"])
    ).run()
    if result.meta.changes == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    return Response(status_code=204)


@app.get("/{path:path}")
async def frontend(path: str, request: Request):
    env = request.scope["env"]
    asset_path = path or "index.html"
    asset_url = f"https://assets.local/{unquote(asset_path)}"
    asset = await env.ASSETS.fetch(asset_url)
    content_type = asset.headers.get("content-type") or "application/octet-stream"
    headers = {"content-type": content_type}
    return Response(content=await asset.bytes(), status_code=asset.status, headers=headers)


Default = asgi.entrypoint(app)
