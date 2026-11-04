import os

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
# The fallback is for local development only; set SECRET_KEY in any real deployment.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")

with app.app_context():
    init_db()
    seed_db()


@app.template_filter("inr")
def inr(value):
    return f"₹{float(value):,.2f}"


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

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Hardcoded data for the UI-only step; real queries arrive in Step 5.
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "November 2026",
    }
    transactions = [
        {"date": "03 Nov 2026", "description": "Weekly groceries", "category": "Food", "amount": 450.00},
        {"date": "02 Nov 2026", "description": "Auto rickshaw to office", "category": "Transport", "amount": 120.00},
        {"date": "30 Oct 2026", "description": "Electricity bill", "category": "Bills", "amount": 1850.00},
        {"date": "27 Oct 2026", "description": "Pharmacy", "category": "Health", "amount": 600.00},
        {"date": "24 Oct 2026", "description": "Movie tickets", "category": "Entertainment", "amount": 499.00},
        {"date": "20 Oct 2026", "description": "New shirt", "category": "Shopping", "amount": 2299.00},
    ]
    stats = {
        "total_spent": 5818.00,
        "transaction_count": 6,
        "top_category": "Shopping",
    }
    categories = [
        {"name": "Shopping", "total": 2299.00, "percent": 39.5},
        {"name": "Bills", "total": 1850.00, "percent": 31.8},
        {"name": "Health", "total": 600.00, "percent": 10.3},
        {"name": "Entertainment", "total": 499.00, "percent": 8.6},
        {"name": "Food", "total": 450.00, "percent": 7.7},
        {"name": "Transport", "total": 120.00, "percent": 2.1},
    ]
    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


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
