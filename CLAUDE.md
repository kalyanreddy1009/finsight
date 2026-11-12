# FinSight — project instructions

The spec is `finsight_v2_0_technical_architecture_and_engineering_specification.md`.
Where this file and the spec disagree, this file wins.

## Client: responsive web app, not a native mobile app

Owner decision, 2026-11-12: "mobile" in the spec means a web page that works well on a phone.
There is no native iOS/Android app.

- Build a mobile-first responsive web app in `web/` (React + Vite + TypeScript), not `mobile/`.
- Dropped from the spec: React Native / Expo, the on-device SQLCipher replica, the Android
  notification listener and iOS payment shortcut, hardware keystore / biometric key storage,
  signed iOS/Android builds.
- The five tabs in spec section 10.1 stay as the navigation structure, laid out for phone
  widths first and scaling up to desktop.
- The web client talks to the FastAPI backend directly. The offline command outbox and
  changelog sync (spec 10.2, `/sync/push`, `/sync/pull`) are deferred until offline use is
  asked for.
- Provisional spend capture becomes a manual quick-add entry in the web app; the
  provisional-to-statement merge on the backend stays.

## Backend deviations from the spec

- Raw `sqlite3` DB-API with versioned SQL migrations in `backend/app/database/migrations/`;
  no SQLAlchemy or Alembic.
- Journal entries are created as `DRAFT` and checked for zero-sum when moved to `POSTED`.
  The spec's per-insert zero-sum trigger is not used (it rejects 3-line entries).
- Lines of a posted entry are immutable; corrections are `REVERSAL` entries.
- No floats in any money path, including the AI privacy bucketing.
- `synchronous = FULL`.

## Commands (from `backend/`)

- Tests: `uv run pytest -q`
- Lint: `uv run ruff check .`

## Git

- Work on feature branches; never push without being asked.
- No AI attribution in commits or PRs.
