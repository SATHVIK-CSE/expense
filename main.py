import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("EXPENSE_DB_PATH", str(BASE_DIR / "expenses.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Expense Tracker API", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            category TEXT NOT NULL,
            expense_date TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")

init_db()

class ExpenseIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=100000000)
    category: Literal["Food", "Transport", "Shopping", "Bills", "Health", "Entertainment", "Other"]
    expense_date: date
    note: str = Field(default="", max_length=300)

class Expense(ExpenseIn):
    id: int

@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.get("/api/expenses", response_model=list[Expense])
def list_expenses(search: str = Query(default="", max_length=100), category: str = "All"):
    sql = "SELECT id, title, amount, category, expense_date, note FROM expenses WHERE 1=1"
    params: list[str] = []
    if search.strip():
        sql += " AND (title LIKE ? OR note LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term])
    if category != "All":
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY expense_date DESC, id DESC"
    with connection() as db:
        return [dict(row) for row in db.execute(sql, params).fetchall()]

@app.post("/api/expenses", response_model=Expense, status_code=201)
def add_expense(expense: ExpenseIn):
    with connection() as db:
        cur = db.execute(
            "INSERT INTO expenses (title, amount, category, expense_date, note) VALUES (?, ?, ?, ?, ?)",
            (expense.title.strip(), expense.amount, expense.category, expense.expense_date.isoformat(), expense.note.strip()),
        )
        row = db.execute("SELECT id, title, amount, category, expense_date, note FROM expenses WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)

@app.delete("/api/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int):
    with connection() as db:
        cur = db.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Expense not found")
