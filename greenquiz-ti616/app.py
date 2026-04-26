from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "greenquiz.sqlite"

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "greenquiz-dev-key")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    db.commit()
    db.close()


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    row = get_db().execute(
        "SELECT id, email, username FROM users WHERE id = ? LIMIT 1", (uid,)
    ).fetchone()
    return row


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_user():
    return {"user": current_user()}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("account"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        errors = []
        if "@" not in email or len(email) < 5:
            errors.append("Email invalide.")
        if len(username) < 2:
            errors.append("Nom utilisateur trop court.")
        if len(password) < 8:
            errors.append("Mot de passe: 8 caracteres minimum.")

        if not errors:
            db = get_db()
            exists = db.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (email,)).fetchone()
            if exists:
                errors.append("Cet email existe deja.")
            else:
                db.execute(
                    "INSERT INTO users (email, username, password_hash) VALUES (?, ?, ?)",
                    # Python build here lacks hashlib.scrypt; force PBKDF2 compatibility.
                    (email, username, generate_password_hash(password, method="pbkdf2:sha256")),
                )
                db.commit()
                uid = db.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (email,)).fetchone()["id"]
                session["uid"] = uid
                return redirect(url_for("account"))

        for err in errors:
            flash(err, "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("account"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT id, password_hash FROM users WHERE email = ? LIMIT 1", (email,)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["uid"] = user["id"]
            return redirect(url_for("account"))

        flash("Identifiants invalides.", "error")

    return render_template("login.html")


@app.route("/account")
@login_required
def account():
    return render_template("account.html", user=current_user())


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8000, debug=False)
