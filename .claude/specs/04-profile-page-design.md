# Spec: Profile Page Design

## Overview
This step replaces the `/profile` stub with a fully designed, login-protected profile page that renders **static, hardcoded data**. It lays out the full UI (user info card, summary stats, recent transactions table and category breakdown) so the design can be reviewed on its own before real database queries are wired in a later step. Login already redirects to `/profile`, so after this step a signed-in user lands on a real page instead of a placeholder string.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables exist in `database/db.py`)
- Step 2: Registration
- Step 3: Login and logout (`session["user_id"]` is set on login; `/logout` clears it)

## Routes
- `GET /profile` — render the profile page with hardcoded context data — logged-in (redirect to `url_for("login")` when `session.get("user_id")` is missing)

No other new routes. The existing `profile` endpoint name must stay the same, because `login`, `register` and `base.html` already link to it.

## Database changes
No database changes. Verified against `database/db.py`: the existing `users` (id, name, email, password_hash, created_at) and `expenses` (id, user_id, amount, category, date, description, created_at) tables already cover every field this page shows. No queries are added in this step.

## Templates
- **Create:** `templates/profile.html`, which extends `base.html` and sets `{% block title %}Profile · Spendly{% endblock %}`. It contains four sections:
  1. **User info card:** avatar circle with initials, name, email and "Member since" date.
  2. **Summary stats row:** three stat cards for total spent (₹), number of transactions and top category.
  3. **Recent transactions table:** columns for date, description, category (as a badge) and amount (₹, right-aligned). At least 5 hardcoded rows.
  4. **Category breakdown:** one row per category with name, ₹ total and a horizontal bar sized by its share of total spend. At least 4 categories.
  - Loads its page stylesheet via `{% block head %}` using `url_for('static', filename='css/profile.css')`.
- **Modify:** none. `base.html` already shows "Profile" and "Sign out" in the navbar when `session.user_id` is set.

## Files to change
- `app.py`: replace the `profile()` stub body with:
  - an auth guard: `if not session.get("user_id"): return redirect(url_for("login"))`
  - hardcoded `user`, `stats`, `transactions` and `categories` Python structures passed to `render_template("profile.html", ...)`

## Files to create
- `templates/profile.html`
- `static/css/profile.css`: all profile-page styles (CLAUDE.md: page-specific styles go in their own `.css` file)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (no queries are expected in this step)
- Passwords hashed with werkzeug (auth is unchanged in this step)
- Use CSS variables — never hardcode hex values (reuse the `:root` tokens in `style.css`: `--ink*`, `--paper*`, `--accent*`, `--border*`, `--radius-*`, `--font-*`)
- All templates extend `base.html`
- Only implement Step 4. Leave the `/expenses/...` stubs untouched.
- No DB access in the route. All data is hardcoded in `app.py` for this design step.
- Currency is INR: every amount is shown with `₹` and Indian digit grouping (e.g. `₹6,398.00`). Never use `$`.
- Hardcoded categories must come from the app's set: Food, Transport, Bills, Health, Entertainment, Shopping, Other.
- Every internal link uses `url_for()`. No hardcoded URLs.
- No inline `style=""` attributes and no `<style>` tags. Category badge colours and bar widths use CSS classes. Pass bar widths as a percentage class or as a CSS custom property set via a class, not inline colour.
- Vanilla JS only. The page should need no JS at all.
- Layout must be responsive: stats and breakdown stack into a single column at mobile widths, and the table scrolls horizontally inside its card instead of overflowing the page.

## Definition of done
- [ ] `python app.py` starts on port 5001 without errors
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects to `/profile` and returns HTTP 200
- [ ] The page shows a user info card with initials avatar, name, email and member-since date
- [ ] The page shows three summary stats: total spent (₹), transaction count and top category
- [ ] The page shows a transactions table with at least 5 rows, each with a category badge and a ₹ amount
- [ ] The page shows a category breakdown with at least 4 categories, each with a ₹ total and a proportional bar
- [ ] The navbar shows "Profile" and "Sign out", and "Sign out" logs the user out and returns to the landing page
- [ ] No `$` symbols appear on the page. All amounts use `₹`.
- [ ] `grep -n '#[0-9a-fA-F]\{3,6\}' templates/profile.html static/css/profile.css` returns no matches
- [ ] `grep -n 'style=' templates/profile.html` returns no matches
- [ ] At a 375px-wide viewport the page has no horizontal page scroll
- [ ] `/expenses/add`, `/expenses/<id>/edit` and `/expenses/<id>/delete` still return their "coming in Step N" placeholder strings
