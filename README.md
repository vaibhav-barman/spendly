# Spendly

A lightweight personal expense tracker built with Flask and SQLite. Amounts are in INR (₹).

**Live demo:** https://spendly-production-9f0f.up.railway.app/

## Features

- Register, log in and log out
- Profile page with your expenses
- Add, edit and delete expenses
- Analytics view of your spending

## Tech stack

- Flask (Python 3.10+)
- SQLite
- Jinja2 templates, vanilla JavaScript, plain CSS
- Deployed on Railway

## Project structure

```
app.py              # All routes
database/db.py      # SQLite helpers
templates/          # Jinja2 templates (extend base.html)
static/             # CSS and JS
tests/              # pytest suite
```

## Run locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The app runs at http://localhost:5001.

## Tests

```bash
pytest
```
