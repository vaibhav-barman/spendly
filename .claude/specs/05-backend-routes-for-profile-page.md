# Spec: Backend Routes for Profile Page

## Overview
Step 4 laid out the `/profile` page with static, hardcoded data. This step wires that page to the real database: the logged-in user's details, their total spend, transaction count, top category, recent transactions and category breakdown are all read from the `users` and `expenses` tables. The page layout and CSS from Step 4 are reused unchanged, so the only visible difference is that the numbers now belong to the signed-in user. All SQL lives in new helpers in `database/db.py`; the route only fetches and renders.

## Depends on
- Step 1: Database setup (`users` and `expenses` tables, `get_db()`, `seed_db()`)
- Step 3: Login and logout (`session["user_id"]`)
- Step 4: Profile page design (`templates/profile.html`, `static/css/profile.css`, auth guard on `/profile`). Note: at the time of writing, these Step 4 files are not present in the working tree. They must exist before this step starts. If they are missing, implement Step 4 first.

## Routes
- `GET /profile` — existing route, now renders real data for the current user — logged-in (redirect to `url_for("login")` if `session.get("user_id")` is missing; if the session user no longer exists in the DB, clear the session and redirect to `url_for("login")`)

No other new routes. The `profile` endpoint name must not change. The `/expenses/...` stubs stay untouched.

## Database changes
No schema changes. Verified against `database/db.py`: `users(id, name, email, password_hash, created_at)` and `expenses(id, user_id, amount, category, date, description, created_at)` already contain every field needed.

New query helpers in `database/db.py` (all take `user_id`, all use `?` placeholders, each opens and closes its own connection via `get_db()`):
- `get_user_by_id(user_id)` — returns `id, name, email, created_at` or `None`
- `get_recent_expenses(user_id, limit=10)` — newest first (`ORDER BY date DESC, id DESC`), returns date, description, category, amount
- `get_expense_summary(user_id)` — returns total spent (0 when no expenses), transaction count, and top category by total (`None` when no expenses)
- `get_category_breakdown(user_id)` — returns category, total and integer percentage of overall spend, highest total first; percentages must be computed safely when total is 0

## Templates
- **Modify:** `templates/profile.html`
  - Replace hardcoded values with the context variables passed from the route (`user`, `stats`, `transactions`, `categories`).
  - Show a friendly empty state when the user has no expenses (no table rows, no bars, stats show `₹0.00`, `0` and `—`).
  - Compute initials for the avatar from `user.name`.
  - Category bar widths remain CSS-class based (e.g. a percentage class); no inline `style=""`.
- **Create:** none

## Files to change
- `database/db.py`: add the four helpers above
- `app.py`: import the helpers, replace the hardcoded data in `profile()` with calls to them, and register an `inr` Jinja filter for Indian digit grouping (e.g. `₹1,23,456.00`)
- `templates/profile.html`: use real context data and add the empty state
- `static/css/profile.css`: only if the empty state or percentage classes need new rules

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only. Never use f-strings in SQL.
- Passwords hashed with werkzeug (auth unchanged; never select or pass `password_hash` to the template)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No DB logic in the route function. It calls the helpers, then renders.
- Scope every query by `user_id` from the session. A user must never see another user's expenses.
- Currency is INR: show `₹` everywhere, never `$`
- Use `abort()` for HTTP errors, not raw string returns
- Only implement the profile page. Leave `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` and `/register` untouched.
- Every internal link uses `url_for()`

## Definition of done
- [ ] `python app.py` starts on port 5001 without errors
- [ ] `/profile` while logged out redirects to `/login`
- [ ] Logging in as `demo@spendly.com` / `demo123` lands on `/profile` with HTTP 200
- [ ] The user card shows the demo user's real name, email and member-since date
- [ ] Total spent for the demo user is `₹6,398.00`, the transaction count is `8`, and the top category is `Shopping`
- [ ] The transactions table lists the demo user's expenses newest first (Dinner out on day 25 appears first)
- [ ] The category breakdown shows each category's ₹ total, and the percentages are consistent with the totals (they sum to about 100)
- [ ] A user with no expenses sees `₹0.00`, `0`, `—` and an empty-state message with no errors
- [ ] A second user's profile never shows the demo user's expenses
- [ ] If the session `user_id` points to a deleted user, `/profile` clears the session and redirects to `/login`
- [ ] `grep -n '\$' templates/profile.html` shows no currency `$` symbols
- [ ] `grep -n 'style=' templates/profile.html` returns no matches
- [ ] `grep -nE '#[0-9a-fA-F]{3,6}' templates/profile.html static/css/profile.css` returns no matches
- [ ] `/expenses/add`, `/expenses/<id>/edit` and `/expenses/<id>/delete` still return their "coming in Step N" placeholder strings
