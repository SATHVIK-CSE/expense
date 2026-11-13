# Cloudflare deployment files

This folder is the Cloudflare Workers version of the expense tracker. It keeps the same HTML/CSS/JavaScript frontend and FastAPI backend, but stores records in Cloudflare D1 (managed SQLite) instead of a local `expenses.db` file.

## Prepare GitHub

Upload the **contents of this `cloudflare` folder** to the root of your GitHub repository (so `worker.py`, `wrangler.jsonc`, `pyproject.toml`, `public/`, and `migrations/` are at the repository root). Replace the old files with these Cloudflare files. Do not upload `expenses.db`.

## Create D1 and bind it

1. In Cloudflare, open **Workers & Pages → D1 SQL Database → Create database**.
2. Name it `xpens-tracker-db`.
3. Copy its database ID.
4. In `wrangler.jsonc`, replace `REPLACE_WITH_YOUR_D1_DATABASE_ID` with that ID. Commit and push the change.
5. Apply the database migration once from a terminal in the repository: `npx wrangler d1 migrations apply xpens-tracker-db --remote` (sign in to Cloudflare if prompted). This creates the `expenses` table.

## Connect GitHub to Cloudflare

1. Open **Workers & Pages → Create application → GitHub** and authorize Cloudflare if asked.
2. Choose your repository and set the root directory to `/`.
3. Set the build command to `uv sync` and deploy command to `uv run pywrangler deploy` if Cloudflare asks for commands. Python Workers use Cloudflare's Python Workers tooling.
4. Save and deploy. Cloudflare gives the site a `workers.dev` URL. Future pushes to the production branch deploy updates.

The D1 binding in `wrangler.jsonc` is named `DB`; keep that name as-is. If setup prompts for a database binding, use `DB` and select `xpens-tracker-db`.
