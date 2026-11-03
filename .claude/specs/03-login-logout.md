# Spec: Login and Logout

## Overview
Implement session-based authentication for Spendly. `POST /login` verifies an email and password against the `users` table and stores the user's id in the Flask session. `GET /logout` clears the session and redirects to the landing page. This is Step 3 of the roadmap: it turns the existing static `login.html` form and the "coming in Step 3" logout placeholder into working features, and gives later steps (profile, add/edit/delete expenses) a way to know who is logged in.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, seeded demo user `demo@spendly.com` / `demo123`).
- Step 2 — Registration (users are created with werkzeug-hashed passwords). Note: `app.py` on `main` currently has no `POST /register` handler. Login can be built and tested with the seeded demo user without it. Do not implement registration as part of this step.

## Routes
- `GET /login` — render the login form; if already logged in, redirect to `/profile` — public
- `POST /login` — validate credentials, set `session["user_id"]`, redirect to `/profile`; on failure re-render `login.html` with a generic error — public
- `GET /logout` — clear the session, redirect to `/` — public (harmless when not logged in)

`/login` and `/logout` already exist in `app.py`. Change them, do not add new routes. `/profile` stays a placeholder ("coming in Step 4"), and is only the redirect target.

## Database changes
No database changes. The existing `users` table (`id`, `name`, `email`, `password_hash`, `created_at`) is sufficient.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — keep the existing form. Keep the `error` block. Repopulate the email input with the submitted value (`value="{{ email or '' }}"`) after a failed attempt. Never repopulate the password.
  - `templates/base.html` — navbar is session-aware. When `session.user_id` is set, show "Profile" (`/profile`) and "Sign out" (`/logout`) instead of "Sign in" / "Get started".

## Files to change
- `app.py` — set `app.secret_key`; import `request`, `session`, `redirect`, `url_for`; implement `login()` (GET + POST) and `logout()`
- `templates/login.html`
- `templates/base.html`

## Files to create
- None

## New dependencies
No new dependencies. Flask sessions and `werkzeug.security.check_password_hash` are already available.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`WHERE email = ?`)
- Passwords hashed with werkzeug: verify with `check_password_hash`, never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Only implement Step 3. Leave `/profile` and the expense routes as placeholders.
- Read the secret key from the `SECRET_KEY` environment variable, with a clearly-labelled dev fallback. Do not hardcode a production secret.
- Normalise email with `.strip().lower()` before lookup.
- Use one generic error message ("Invalid email or password") for both an unknown email and a wrong password, to avoid account enumeration.
- Use `get_db()` and close the connection in a `finally` block, matching `database/db.py`.
- Store only `user_id` in the session. Call `session.clear()` on logout, and before setting `user_id` on login to prevent session fixation.
- Any `next` redirect parameter is out of scope. Always redirect to `/profile` after login.
- Put CSS changes (if any, e.g. for navbar user link) in `static/css/style.css` only.
- Currency/copy conventions (INR ₹) are unaffected by this step.

## Definition of done
- [ ] `python3 app.py` or `uv run app.py` starts on port 5001 with no errors
- [ ] `GET /login` renders the sign-in form
- [ ] Submitting `demo@spendly.com` / `demo123` redirects to `/profile` (placeholder text is shown)
- [ ] Email matching is case- and whitespace-insensitive (`  Demo@Spendly.com ` works)
- [ ] A wrong password shows "Invalid email or password" on the login page, and the email field keeps its value while the password field is empty
- [ ] An unknown email shows the same "Invalid email or password" message
- [ ] After login, the navbar shows "Profile" and "Sign out", and does not show "Sign in" / "Get started"
- [ ] `GET /login` while logged in redirects to `/profile`
- [ ] `GET /logout` redirects to `/`, and the navbar goes back to "Sign in" / "Get started"
- [ ] After logout, the browser's session cookie no longer authenticates (visiting `/login` shows the form, not a redirect)
- [ ] `GET /logout` while logged out redirects to `/` without error
- [ ] No hardcoded hex colours were added, and no SQL is built with string formatting
