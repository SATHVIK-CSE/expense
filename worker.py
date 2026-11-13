from datetime import date
from typing import Literal
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from workers import asgi

app = FastAPI(title="Spendwise Expense Tracker")

class ExpenseIn(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    amount: float = Field(gt=0, le=100000000)
    category: Literal["Food", "Transport", "Shopping", "Bills", "Health", "Entertainment", "Other"]
    expense_date: date
    note: str = Field(default="", max_length=300)

async def d1(request: Request):
    return request.scope["env"].DB

@app.get("/api/expenses")
async def list_expenses(request: Request, search: str = Query(default="", max_length=100), category: str = "All"):
    db = await d1(request)
    sql = "SELECT id, title, amount, category, expense_date, note FROM expenses WHERE 1=1"
    values = []
    if search.strip():
        sql += " AND (title LIKE ? OR note LIKE ?)"
        term = f"%{search.strip()}%"
        values.extend([term, term])
    if category != "All":
        sql += " AND category = ?"
        values.append(category)
    sql += " ORDER BY expense_date DESC, id DESC"
    statement = db.prepare(sql)
    if values:
        statement = statement.bind(*values)
    result = await statement.run()
    return result.results

@app.post("/api/expenses", status_code=201)
async def add_expense(expense: ExpenseIn, request: Request):
    db = await d1(request)
    await db.prepare("INSERT INTO expenses (title, amount, category, expense_date, note) VALUES (?, ?, ?, ?, ?)").bind(
        expense.title.strip(), expense.amount, expense.category, expense.expense_date.isoformat(), expense.note.strip()
    ).run()
    result = await db.prepare("SELECT id, title, amount, category, expense_date, note FROM expenses ORDER BY id DESC LIMIT 1").run()
    return result.results[0]

@app.delete("/api/expenses/{expense_id}", status_code=204)
async def delete_expense(expense_id: int, request: Request):
    db = await d1(request)
    result = await db.prepare("DELETE FROM expenses WHERE id = ?").bind(expense_id).run()
    if result.meta.changes == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    return Response(status_code=204)

@app.get("/{path:path}")
async def frontend(path: str, request: Request):
    env = request.scope["env"]
    asset_path = path or "index.html"
    asset_url = f"https://assets.local/{unquote(asset_path)}"
    response = await env.ASSETS.fetch(asset_url)
    return Response(content=await response.bytes(), status_code=response.status, headers=response.headers)

Default = asgi.entrypoint(app)
