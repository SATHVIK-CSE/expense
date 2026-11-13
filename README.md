# Expense tracker (HTML, CSS, JavaScript, FastAPI, SQLite)

A small personal expense tracker. FastAPI serves the website and JSON API; SQLite stores expenses in `expenses.db` next to `main.py`.

## Run locally

1. Install Python 3.10 or newer.
2. In this folder, create and activate a virtual environment:
   - Windows: `py -m venv .venv` then `.venv\Scripts\Activate.ps1`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Start the site: `uvicorn main:app --reload`
5. Open http://127.0.0.1:8000

The API docs are at http://127.0.0.1:8000/docs. SQLite creates its database file automatically on first run.

## Deploy

Deploy this folder to a Python web host that supports persistent storage. Set the start command to `uvicorn main:app --host 0.0.0.0 --port $PORT` (use the host's documented port variable syntax). Mount persistent storage and set `EXPENSE_DB_PATH` to a file on that volume, such as `/var/data/expenses.db`. Without persistent storage, SQLite data may be lost on redeploy. For a public multi-user site, add authentication and use a managed database before launch; this starter is intended for a personal/demo tracker.
