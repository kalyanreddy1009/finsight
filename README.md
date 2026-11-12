# FinSight

FinSight is a local-first personal finance ledger. Every money movement is a balanced double-entry
journal entry stored as integer paise, and it runs on your own machine with a FastAPI backend and
a mobile-first React web client.

The full specification is in [finsight_v2_0_technical_architecture_and_engineering_specification.md](finsight_v2_0_technical_architecture_and_engineering_specification.md).
[CLAUDE.md](CLAUDE.md) overrides it where they differ.

## Status

| Area | Status | Notes |
|---|---|---|
| Ledger engine | Built | Double-entry journal, `DRAFT` to `POSTED`, reversals, integer paise |
| Auth | Built | Single owner, setup, login, refresh, logout, device list and revoke |
| Accounts | Built | Asset and liability subtypes, optional opening balance |
| Categories | Built | List and create (Plan tab) |
| Transactions | Built | Expense, income, transfer, refund; expense splits; settle split; reverse; edit notes, tax section and category |
| Statement import | Built, CSV only | Upload, row review, commit once reconciled |
| Dashboard | Built | Safe-to-spend summary |
| Web client | Built | Home, Transactions, Accounts, Plan tabs |
| Bank and card PDF parsers | Not built | PDF uploads are rejected (`NO_PARSER`); needs sample statements |
| Budgets | Not built | |
| Recurring bills and price-creep detection | Not built | |
| Goals | Not built | |
| Investments, CAS import, XIRR screens | Not built | `backend/app/finance/xirr_engine.py` exists; no endpoint or screen uses it |
| Tax summary | Not built | Tax section is stored per transaction; no summary endpoint |
| AI assistant | Not built | Assistant tab is a placeholder; `backend/app/ai/privacy_filter.py` is not wired to any route |
| Offline sync | Not built | `/sync/*` is deferred per CLAUDE.md |
| Backend serving the web build | Not built | Only the Vite dev server is set up |
| Docker deployment | Not built | No Dockerfile |
| SQLCipher encryption at rest | Not built | `FINSIGHT_DB_DRIVER=sqlcipher` switch exists, but `sqlcipher3` is not a declared dependency; default is plain SQLite |

## Requirements

- Python 3.12 (`backend/.python-version`, `requires-python = ">=3.12"`) and [uv](https://docs.astral.sh/uv/).
  Checked with uv 0.13.6.
- Node.js and npm. The repo does not pin a Node version (no `engines` field, no `.nvmrc`).
  Checked with Node 26.13.0 and npm 11.20.0. The lockfile is npm `lockfileVersion` 3, so use npm 7 or later.

## Run the backend

Run these from `backend/`:

```bash
cd backend
uv sync
```

Set the environment variables (see the table below) in the same shell, then start the server:

```bash
uv run uvicorn app.main:create_app --factory --reload
```

The API listens on `http://127.0.0.1:8000`. Check it with:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

The database is created and migrated on startup. OpenAPI docs are disabled.
In PowerShell, set variables with `$env:NAME = "value"` instead of `export NAME=value`.

### Environment variables

Settings are read from `FINSIGHT_*` environment variables only. The app does not read a `.env` file.

| Variable | Required | What it is | How to get a value |
|---|---|---|---|
| `FINSIGHT_JWT_SECRET` | Yes | Signs access tokens. At least 32 bytes. The API refuses to start without it. | `uv run python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `FINSIGHT_SETUP_TOKEN` | Yes, for first run | One-time code you choose. Typed into the Setup Code field on the first-run Setup screen. Without it, `/api/v1/auth/setup` returns 503. Once the owner exists, setup returns 409. | Choose any long random string, for example the output of the command above |
| `FINSIGHT_MASTER_KEY` | Yes, for statement upload | 32-byte key as 64 hex characters. Encrypts stored statement files with AES-256-GCM. Without it, uploads return 503 `STORAGE_NOT_CONFIGURED`. Losing it makes stored files unreadable. | `uv run python -c "import secrets; print(secrets.token_hex(32))"` |
| `FINSIGHT_DB_PATH` | No | SQLite database file. Default `finsight.db`, relative to the working directory (`backend/` in the commands above). | Path you choose |
| `FINSIGHT_DOCS_DIR` | No | Folder for stored statement files. Default `docs_store`, relative to the working directory. | Path you choose |
| `FINSIGHT_DB_DRIVER` | No | `sqlite` (default) or `sqlcipher`. The `sqlcipher` option needs the `sqlcipher3` package, which you must install yourself. | Leave unset |
| `FINSIGHT_DB_KEY` | No | Passphrase for SQLCipher. Only used when `FINSIGHT_DB_DRIVER=sqlcipher`. | Any long random string |
| `FINSIGHT_ALLOWED_ORIGINS` | No | JSON list of browser origins allowed to call the API. Empty by default. `"*"` is refused. The Vite dev proxy does not need it. | `'["http://localhost:5173"]'` |
| `FINSIGHT_CLOUD_AI_ENABLED` | No | Read into settings but nothing uses it yet. | Leave unset |

Example, with placeholder values only (bash):

```bash
export FINSIGHT_JWT_SECRET='replace-with-a-random-string-of-at-least-32-bytes'
export FINSIGHT_SETUP_TOKEN='replace-with-your-setup-code'
export FINSIGHT_MASTER_KEY='0000000000000000000000000000000000000000000000000000000000000000'
export FINSIGHT_DB_PATH="$HOME/finsight-data/finsight.db"
export FINSIGHT_DOCS_DIR="$HOME/finsight-data/docs_store"
```

The all-zero master key above is a placeholder. Generate a real one for any actual use.
Keep the database and document folders outside the repository. The root `.gitignore` ignores `*.db`
and `docs_store/` as a backstop.

### FINSIGHT_SETUP_TOKEN

The setup token is a code you choose before the first start; the server does not issue it. The
first-run Setup screen asks for it in the Setup Code field. The owner account is created only if it
matches. After setup, `/auth/setup` refuses further requests, so the variable can be removed.

## Run the web client

Run these from `web/`:

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173`. That is the Vite default; `web/vite.config.ts` does not set a port.
The dev server proxies every `/api` request to `http://127.0.0.1:8000`, so start the backend first and
use the Vite URL in the browser. The browser never calls the backend port directly.

## First run

1. Start the backend with `FINSIGHT_JWT_SECRET`, `FINSIGHT_SETUP_TOKEN` and `FINSIGHT_MASTER_KEY` set.
2. Open `http://localhost:5173`. The Setup screen appears because no owner exists yet.
3. Enter a password of at least 12 characters, confirm it, give this browser a name, and enter the
   setup code from `FINSIGHT_SETUP_TOKEN`.
4. On the Accounts tab, add an account and pick a subtype such as `BANK_SAVINGS` or `CREDIT_CARD`.
5. On the Plan tab, add a category (expense or income).
6. On the Transactions tab, add a transaction with quick add. Choose the account and category.
7. On the Accounts tab, upload a `.csv` statement for an account with the CSV file type. Review the
   rows, then commit. Commit is refused with 409 `STATEMENT_NOT_RECONCILED` until the statement
   reconciles to its closing balance, has no import errors, and has no rows pending review.

### CSV statement format

The parser is `backend/app/ingestion/csv_parser.py`. Header matching is case-insensitive and
ignores extra spaces. Each column may use any of these names:

- **Date** (required): `date`, `txn date`, `transaction date`, `value date`
- **Description** (required): `description`, `narration`, `particulars`, `remarks`
- **Amounts**, either split or single:
  - Split: a debit column (`debit`, `withdrawal`, `withdrawal amt`, `dr`) and a credit column
    (`credit`, `deposit`, `deposit amt`, `cr`).
  - Single: an `amount` column. A negative value is a debit.
- **Balance** (optional, used for reconciliation): `balance`, `closing balance`, `running balance`

Also: UTF-8 (a BOM is accepted); day-first dates such as `31/12/2026`, `2026-12-31`, `31-Dec-2026`
or `31/12/26`; amounts in rupees with at most two decimals, optionally with a `₹`, `INR` or `Rs` prefix,
a `Cr`/`Dr` suffix or commas; exactly one of debit or credit above zero per row. Newest-first files are
reversed automatically. Limits: 25 MB and 20,000 data rows.

## Security notes

- The refresh cookie `fs_refresh` is `HttpOnly`, `Secure` and `SameSite=Strict`. Browsers keep `Secure`
  cookies only on HTTPS or `http://localhost`, so use one of those. On a LAN address over plain HTTP the
  session will not persist.
- Run Setup before exposing the port. Until the owner exists, the setup code is the only protection.
- Login throttling is in memory: 5 failed attempts per client address and 50 across all addresses, per
  15 minutes. Setup-code failures count too. Counters reset on restart. `X-Forwarded-For` is not trusted.
- Secrets come only from environment variables. Do not commit them or put them in a `.env` file.
- Nothing is sent to an external service. The backend makes no outbound HTTP calls.

## Tests and checks

Backend, from `backend/`:

```bash
uv run pytest -q
uv run ruff check .
```

Web, from `web/`:

```bash
npm run typecheck
npm run lint
npm test
npm run build
```

`npm run build` runs the type check and then `vite build`, writing to `web/dist/`.

## Project layout

```text
finsight/
├── backend/   FastAPI app, ledger, ingestion and pytest suite (uv project)
├── web/       React, Vite and TypeScript client (npm project)
├── docs/      web-design-rules.md, the rules the web client follows
└── CLAUDE.md  project instructions and deviations from the spec
```

## Deviations from the spec

The full list is in [CLAUDE.md](CLAUDE.md). In short:

- The client is a responsive web app in `web/`, not a native iOS or Android app.
- Raw `sqlite3` with versioned SQL migrations in `backend/app/database/migrations/`; no SQLAlchemy or Alembic.
- Journal entries start as `DRAFT` and are zero-sum checked when `POSTED`. Posted lines are immutable;
  corrections are reversal entries.
- No floats in any money path. Amounts are integer paise.
