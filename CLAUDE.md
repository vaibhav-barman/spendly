# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Spendly: a Flask expense tracker built as a numbered, step-by-step scaffold (Step 1 = database setup, Step 3 = logout, Step 4 = profile, Steps 7–9 = add/edit/delete expenses).

## Commands

- Python 3.14, virtualenv at `.venv/` (already has Flask). Install deps with `.venv/bin/pip install -r requirements.txt`.
- Run: `python app.py`: Flask dev server with debug on, **port 5001** (not 5000).
- Test: `pytest` (pytest + pytest-flask). Single test: `pytest path/to/test_file.py::test_name`. No tests exist yet.
- `pyproject.toml`, `uv.lock` and `src/expense_tracker/` are an unrelated uv skeleton. Don't add Flask deps there; `requirements.txt` is the source of truth.

## Architecture

- `app.py` is the entry point and holds every route. Placeholder routes return strings like "coming in Step N".
- **Only implement the step you were asked for.** Don't fill in other placeholder routes.
- `database/db.py` is currently a stub. It is meant to hold `get_db()` (SQLite connection with `row_factory` and foreign keys on), `init_db()` (`CREATE TABLE IF NOT EXISTS`) and `seed_db()` (sample dev data).
- Templates in `templates/` extend `base.html`, which provides the `title`, `head`, `content` and `scripts` blocks plus the shared navbar and footer. Put page-specific JS inline in `{% block scripts %}`. `static/js/main.js` is an empty global placeholder.
- All CSS lives in the single `static/css/style.css`; the legal pages (terms, privacy) share styles. Don't add separate CSS files.
- Currency is INR (₹) everywhere: UI copy, mock data and seed data.

## Git

- Commit messages use a lowercase `area: message` prefix, e.g. `landing: add youtube modal`.
