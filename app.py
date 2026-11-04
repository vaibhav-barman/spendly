import calendar
import os
from datetime import date, datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    get_category_breakdown,
    get_db,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
# The fallback is for local development only; set SECRET_KEY in any real deployment.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

with app.app_context():
    init_db()
    seed_db()


@app.template_filter("inr")
def inr_filter(value):
    """Format a number as rupees with Indian digit grouping, e.g. ₹1,23,456.00."""
    amount = float(value or 0)
    sign = "-" if amount < 0 else ""
    whole, frac = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}₹{whole}.{frac}"


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register")
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password", email=email
        )

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

def _parse_iso_date(value):
    """Return value as a normalised YYYY-MM-DD string, or None if missing/invalid."""
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _parse_date_range(args):
    """Read date_from / date_to from the query string.

    Each bound is validated on its own; a missing or malformed one is an open
    bound. Returns (date_from, date_to, error). An inverted range clears both
    bounds and reports an error.
    """
    date_from = _parse_iso_date(args.get("date_from"))
    date_to = _parse_iso_date(args.get("date_to"))
    if date_from and date_to and date_from > date_to:
        return None, None, "Start date must be before end date."
    return date_from, date_to, None


def _build_presets(today):
    """Quick-pick ranges, aligned to calendar months and ending on the last day
    of the current month. All Time has no bounds (a clean /profile URL)."""
    def month_start(months_back):
        year, month = divmod(today.year * 12 + today.month - 1 - months_back, 12)
        return date(year, month + 1, 1).isoformat()

    month_end = date(
        today.year, today.month, calendar.monthrange(today.year, today.month)[1]
    ).isoformat()

    presets = [
        {"key": key, "label": label, "date_from": month_start(back), "date_to": month_end}
        for key, label, back in (
            ("month", "This Month", 0),
            ("3m", "Last 3 Months", 2),
            ("6m", "Last 6 Months", 5),
        )
    ]
    presets.append({"key": "all", "label": "All Time", "date_from": None, "date_to": None})
    return presets


def _build_profile_user(row):
    parts = row["name"].split()
    initials = "".join(p[0] for p in parts[:2]).upper() or "?"
    try:
        member_since = datetime.strptime(
            row["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
    except (TypeError, ValueError):
        member_since = "—"
    return {
        "initials": initials,
        "name": row["name"],
        "email": row["email"],
        "member_since": member_since,
    }


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user_row = get_user_by_id(user_id)
    if user_row is None:
        session.clear()
        return redirect(url_for("login"))

    date_from, date_to, filter_error = _parse_date_range(request.args)
    presets = _build_presets(date.today())
    active_key = next(
        (
            p["key"]
            for p in presets
            if (p["date_from"], p["date_to"]) == (date_from, date_to)
        ),
        None,
    )

    return render_template(
        "profile.html",
        user=_build_profile_user(user_row),
        stats=get_expense_summary(user_id, date_from=date_from, date_to=date_to),
        transactions=get_recent_expenses(user_id, date_from=date_from, date_to=date_to),
        categories=get_category_breakdown(user_id, date_from=date_from, date_to=date_to),
        date_from=date_from,
        date_to=date_to,
        is_filtered=bool(date_from or date_to),
        presets=presets,
        active_key=active_key,
        filter_error=filter_error,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
