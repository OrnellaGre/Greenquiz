from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "greenquiz.sqlite"
PAGE_SIZE = 20
ALLOWED_DIFFICULTIES = {"facile", "moyen", "difficile"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "greenquiz-dev-key")
SEARCH_CACHE: dict[str, tuple[list[sqlite3.Row], int]] = {}


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


def clear_search_cache() -> None:
    SEARCH_CACHE.clear()


def table_has_column(db: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    for row in rows:
        if row[1] == column_name:
            return True
    return False


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL,
            description TEXT NOT NULL,
            id_createur INTEGER NOT NULL,
            date_creation TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            difficulte TEXT NOT NULL CHECK(difficulte IN ('facile', 'moyen', 'difficile')),
            categorie TEXT NOT NULL,
            est_publique INTEGER NOT NULL DEFAULT 1,
            nombre_questions INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(id_createur) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_quiz INTEGER NOT NULL,
            texte TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('QCM', 'vrai/faux', 'reponse_courte')),
            reponses_possibles TEXT,
            reponse_correcte TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(id_quiz) REFERENCES quizzes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS sessions_quiz (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_utilisateur INTEGER,
            id_quiz INTEGER NOT NULL,
            score INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(id_utilisateur) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY(id_quiz) REFERENCES quizzes(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_quizzes_creator ON quizzes(id_createur);
        CREATE INDEX IF NOT EXISTS idx_quizzes_public_date ON quizzes(est_publique, date_creation);
        CREATE INDEX IF NOT EXISTS idx_quizzes_category ON quizzes(categorie);
        CREATE INDEX IF NOT EXISTS idx_questions_quiz ON questions(id_quiz);
        CREATE INDEX IF NOT EXISTS idx_sessions_quiz ON sessions_quiz(id_quiz);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions_quiz(id_utilisateur);
        """
    )
    if not table_has_column(db, "users", "is_admin"):
        db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    if not table_has_column(db, "quizzes", "nombre_questions"):
        db.execute("ALTER TABLE quizzes ADD COLUMN nombre_questions INTEGER NOT NULL DEFAULT 0")
    db.commit()
    db.close()


init_db()


def parse_page() -> int:
    raw = request.args.get("page", "1")
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))


def parse_questions_payload(payload: str) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    if not payload.strip():
        return [], ["Au moins une question est obligatoire."]
    try:
        loaded = json.loads(payload)
    except json.JSONDecodeError:
        return [], ["Le JSON des questions est invalide."]
    if not isinstance(loaded, list) or not loaded:
        return [], ["Le JSON des questions doit etre une liste non vide."]
    valid_questions: list[dict] = []
    for idx, item in enumerate(loaded, start=1):
        if not isinstance(item, dict):
            errors.append(f"Question {idx}: format invalide.")
            continue
        qtype = str(item.get("type", "")).strip()
        texte = str(item.get("texte", "")).strip()
        reponse = str(item.get("reponse_correcte", "")).strip()
        points_raw = item.get("points", 1)
        try:
            points = int(points_raw)
        except (TypeError, ValueError):
            points = 0
        possibles = item.get("reponses_possibles", [])
        if qtype not in {"QCM", "vrai/faux", "reponse_courte"}:
            errors.append(f"Question {idx}: type invalide.")
        if len(texte) < 3:
            errors.append(f"Question {idx}: enonce trop court.")
        if not reponse:
            errors.append(f"Question {idx}: reponse correcte manquante.")
        if points < 1:
            errors.append(f"Question {idx}: points invalides.")
        if qtype == "QCM":
            if not isinstance(possibles, list) or len(possibles) < 2:
                errors.append(f"Question {idx}: un QCM demande au moins 2 reponses.")
        elif not isinstance(possibles, list):
            possibles = []
        valid_questions.append(
            {
                "type": qtype,
                "texte": texte,
                "reponse_correcte": reponse,
                "points": points,
                "reponses_possibles": possibles,
            }
        )
    return valid_questions, errors


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return get_db().execute(
        "SELECT id, email, username, is_admin FROM users WHERE id = ? LIMIT 1", (uid,)
    ).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if not user["is_admin"]:
            return redirect(url_for("home"))
        return view(*args, **kwargs)

    return wrapped


def can_manage_quiz(quiz_row: sqlite3.Row, user: sqlite3.Row | None) -> bool:
    if not user:
        return False
    return bool(user["is_admin"] or quiz_row["id_createur"] == user["id"])


@app.context_processor
def inject_user():
    return {"user": current_user()}


@app.errorhandler(400)
def bad_request(_):
    return render_template("error.html", code=400, message="Requete invalide."), 400


@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="Acces refuse."), 403


@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="Ressource introuvable."), 404


@app.route("/")
def home():
    page = parse_page()
    offset = (page - 1) * PAGE_SIZE
    q = request.args.get("q", "").strip().lower()
    difficulty = request.args.get("difficulte", "").strip().lower()
    category = request.args.get("categorie", "").strip()
    filters: list[str] = ["est_publique = 1"]
    params: list[object] = []
    if q:
        filters.append("(LOWER(titre) LIKE ? OR LOWER(description) LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like])
    if difficulty in ALLOWED_DIFFICULTIES:
        filters.append("difficulte = ?")
        params.append(difficulty)
    if category:
        filters.append("categorie = ?")
        params.append(category)
    where_clause = " AND ".join(filters)
    cache_key = f"{where_clause}|{tuple(params)}|{page}"
    if cache_key in SEARCH_CACHE:
        quizzes, total_count = SEARCH_CACHE[cache_key]
    else:
        db = get_db()
        total_count = db.execute(
            f"SELECT COUNT(*) AS c FROM quizzes WHERE {where_clause}", params
        ).fetchone()["c"]
        quizzes = db.execute(
            f"""
            SELECT id, titre, description, difficulte, categorie, date_creation
            FROM quizzes
            WHERE {where_clause}
            ORDER BY date_creation DESC
            LIMIT ? OFFSET ?
            """,
            (*params, PAGE_SIZE, offset),
        ).fetchall()
        SEARCH_CACHE[cache_key] = (quizzes, total_count)

    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    return render_template(
        "index.html",
        quizzes=quizzes,
        page=page,
        total_pages=total_pages,
        filters={"q": q, "difficulte": difficulty, "categorie": category},
    )


@app.route("/auth/register", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        errors = []
        if not validate_email(email):
            errors.append("Email invalide.")
        if len(username) < 2:
            errors.append("Nom utilisateur trop court.")
        if len(password) < 8:
            errors.append("Mot de passe: 8 caracteres minimum.")
        db = get_db()
        if not errors:
            exists = db.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (email,)).fetchone()
            if exists:
                errors.append("Cet email existe deja.")
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("register.html")
        users_count = db.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        is_admin = 1 if users_count == 0 else 0
        db.execute(
            "INSERT INTO users (email, username, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            (email, username, generate_password_hash(password, method="pbkdf2:sha256"), is_admin),
        )
        db.commit()
        clear_search_cache()
        created = db.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (email,)).fetchone()
        session["uid"] = created["id"]
        return redirect(url_for("account"))
    return render_template("register.html")


@app.route("/auth/login", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("account"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
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


@app.route("/auth/logout")
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/account")
@login_required
def account():
    user = current_user()
    return render_template("account.html", user=user)


@app.route("/account/edit", methods=["GET", "POST"])
@login_required
def account_edit():
    user = current_user()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        errors = []
        if not validate_email(email):
            errors.append("Email invalide.")
        if len(username) < 2:
            errors.append("Nom utilisateur trop court.")
        db = get_db()
        if not errors:
            existing = db.execute(
                "SELECT id FROM users WHERE email = ? AND id <> ? LIMIT 1", (email, user["id"])
            ).fetchone()
            if existing:
                errors.append("Cet email est deja utilise.")
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("account_edit.html", user=user)
        db.execute("UPDATE users SET email = ?, username = ? WHERE id = ?", (email, username, user["id"]))
        db.commit()
        flash("Profil mis a jour.", "ok")
        return redirect(url_for("account"))
    return render_template("account_edit.html", user=user)


@app.route("/users")
@admin_required
def users_list():
    page = parse_page()
    offset = (page - 1) * PAGE_SIZE
    search = request.args.get("q", "").strip().lower()
    db = get_db()
    where = ""
    params: list[object] = []
    if search:
        where = "WHERE LOWER(username) LIKE ? OR LOWER(email) LIKE ?"
        like = f"%{search}%"
        params.extend([like, like])
    total = db.execute(f"SELECT COUNT(*) AS c FROM users {where}", params).fetchone()["c"]
    users = db.execute(
        f"""
        SELECT id, username, email, is_admin, created_at
        FROM users
        {where}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, PAGE_SIZE, offset),
    ).fetchall()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return render_template("users_list.html", users=users, page=page, total_pages=total_pages, q=search)


@app.route("/users/new", methods=["GET", "POST"])
@admin_required
def users_new():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        is_admin = 1 if request.form.get("is_admin") == "on" else 0
        errors = []
        if not validate_email(email):
            errors.append("Email invalide.")
        if len(username) < 2:
            errors.append("Nom utilisateur trop court.")
        if len(password) < 8:
            errors.append("Mot de passe: 8 caracteres minimum.")
        db = get_db()
        if not errors:
            exists = db.execute("SELECT id FROM users WHERE email = ? LIMIT 1", (email,)).fetchone()
            if exists:
                errors.append("Cet email existe deja.")
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("users_form.html", edit_user=None)
        db.execute(
            "INSERT INTO users (email, username, password_hash, is_admin) VALUES (?, ?, ?, ?)",
            (email, username, generate_password_hash(password, method="pbkdf2:sha256"), is_admin),
        )
        db.commit()
        flash("Utilisateur cree.", "ok")
        return redirect(url_for("users_list"))
    return render_template("users_form.html", edit_user=None)


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def users_edit(user_id: int):
    db = get_db()
    edit_user = db.execute(
        "SELECT id, email, username, is_admin FROM users WHERE id = ? LIMIT 1", (user_id,)
    ).fetchone()
    if not edit_user:
        abort(404)
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        is_admin = 1 if request.form.get("is_admin") == "on" else 0
        new_password = request.form.get("password", "")
        errors = []
        if not validate_email(email):
            errors.append("Email invalide.")
        if len(username) < 2:
            errors.append("Nom utilisateur trop court.")
        exists = db.execute("SELECT id FROM users WHERE email = ? AND id <> ? LIMIT 1", (email, user_id)).fetchone()
        if exists:
            errors.append("Cet email est deja utilise.")
        if new_password and len(new_password) < 8:
            errors.append("Mot de passe: 8 caracteres minimum.")
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("users_form.html", edit_user=edit_user)
        if new_password:
            db.execute(
                "UPDATE users SET email = ?, username = ?, is_admin = ?, password_hash = ? WHERE id = ?",
                (email, username, is_admin, generate_password_hash(new_password, method="pbkdf2:sha256"), user_id),
            )
        else:
            db.execute(
                "UPDATE users SET email = ?, username = ?, is_admin = ? WHERE id = ?",
                (email, username, is_admin, user_id),
            )
        db.commit()
        flash("Utilisateur modifie.", "ok")
        return redirect(url_for("users_list"))
    return render_template("users_form.html", edit_user=edit_user)


@app.route("/users/<int:user_id>/delete", methods=["GET", "POST"])
@admin_required
def users_delete(user_id: int):
    db = get_db()
    target = db.execute("SELECT id, username FROM users WHERE id = ? LIMIT 1", (user_id,)).fetchone()
    if not target:
        abort(404)
    if request.method == "POST":
        confirmed = request.form.get("confirm") == "yes"
        if not confirmed:
            flash("Confirmation obligatoire.", "error")
            return render_template("users_delete.html", target=target)
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        flash("Utilisateur supprime.", "ok")
        return redirect(url_for("users_list"))
    return render_template("users_delete.html", target=target)


@app.route("/quizzes")
def quizzes_list():
    page = parse_page()
    offset = (page - 1) * PAGE_SIZE
    q = request.args.get("q", "").strip().lower()
    user = current_user()
    db = get_db()
    filters: list[str] = []
    params: list[object] = []
    if user and user["is_admin"]:
        filters.append("1 = 1")
    elif user:
        filters.append("(q.est_publique = 1 OR q.id_createur = ?)")
        params.append(user["id"])
    else:
        filters.append("q.est_publique = 1")
    if q:
        filters.append("LOWER(q.titre) LIKE ?")
        params.append(f"%{q}%")
    where = " AND ".join(filters)
    total = db.execute(f"SELECT COUNT(*) AS c FROM quizzes q WHERE {where}", params).fetchone()["c"]
    quizzes = db.execute(
        f"""
        SELECT q.id, q.titre, q.categorie, q.difficulte, q.est_publique, q.id_createur, u.username AS createur
        FROM quizzes q
        JOIN users u ON u.id = q.id_createur
        WHERE {where}
        ORDER BY q.date_creation DESC
        LIMIT ? OFFSET ?
        """,
        (*params, PAGE_SIZE, offset),
    ).fetchall()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return render_template("quizzes_list.html", quizzes=quizzes, page=page, total_pages=total_pages, q=q)


@app.route("/quizzes/new", methods=["GET", "POST"])
@login_required
def quizzes_new():
    user = current_user()
    if request.method == "POST":
        titre = request.form.get("titre", "").strip()
        description = request.form.get("description", "").strip()
        difficulte = request.form.get("difficulte", "").strip().lower()
        categorie = request.form.get("categorie", "").strip()
        est_publique = 1 if request.form.get("est_publique") == "on" else 0
        raw_questions = request.form.get("questions_json", "").strip()
        questions, q_errors = parse_questions_payload(raw_questions)
        errors = list(q_errors)
        if len(titre) < 3:
            errors.append("Titre trop court.")
        if len(description) < 10:
            errors.append("Description trop courte.")
        if difficulte not in ALLOWED_DIFFICULTIES:
            errors.append("Difficulte invalide.")
        if len(categorie) < 2:
            errors.append("Categorie invalide.")
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("quizzes_form.html", edit_quiz=None, questions_json=raw_questions)
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO quizzes (titre, description, id_createur, date_creation, difficulte, categorie, est_publique)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (titre, description, user["id"], datetime.utcnow().isoformat(), difficulte, categorie, est_publique),
        )
        quiz_id = cursor.lastrowid
        for question in questions:
            db.execute(
                """
                INSERT INTO questions (id_quiz, texte, type, reponses_possibles, reponse_correcte, points)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    quiz_id,
                    question["texte"],
                    question["type"],
                    json.dumps(question["reponses_possibles"], ensure_ascii=True),
                    question["reponse_correcte"],
                    question["points"],
                ),
            )
        db.execute("UPDATE quizzes SET nombre_questions = ? WHERE id = ?", (len(questions), quiz_id))
        db.commit()
        clear_search_cache()
        flash("Quiz cree.", "ok")
        return redirect(url_for("quizzes_list"))
    sample = '[{"texte":"2+2 ?","type":"QCM","reponses_possibles":["3","4"],"reponse_correcte":"4","points":1}]'
    return render_template("quizzes_form.html", edit_quiz=None, questions_json=sample)


@app.route("/quizzes/<int:quiz_id>/edit", methods=["GET", "POST"])
@login_required
def quizzes_edit(quiz_id: int):
    db = get_db()
    quiz = db.execute(
        """
        SELECT id, titre, description, difficulte, categorie, est_publique, id_createur
        FROM quizzes
        WHERE id = ? LIMIT 1
        """,
        (quiz_id,),
    ).fetchone()
    if not quiz:
        abort(404)
    user = current_user()
    if not can_manage_quiz(quiz, user):
        abort(403)
    if request.method == "POST":
        titre = request.form.get("titre", "").strip()
        description = request.form.get("description", "").strip()
        difficulte = request.form.get("difficulte", "").strip().lower()
        categorie = request.form.get("categorie", "").strip()
        est_publique = 1 if request.form.get("est_publique") == "on" else 0
        raw_questions = request.form.get("questions_json", "").strip()
        questions, q_errors = parse_questions_payload(raw_questions)
        errors = list(q_errors)
        if len(titre) < 3:
            errors.append("Titre trop court.")
        if len(description) < 10:
            errors.append("Description trop courte.")
        if difficulte not in ALLOWED_DIFFICULTIES:
            errors.append("Difficulte invalide.")
        if len(categorie) < 2:
            errors.append("Categorie invalide.")
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("quizzes_form.html", edit_quiz=quiz, questions_json=raw_questions)
        db.execute(
            "UPDATE quizzes SET titre = ?, description = ?, difficulte = ?, categorie = ?, est_publique = ?, nombre_questions = ? WHERE id = ?",
            (titre, description, difficulte, categorie, est_publique, len(questions), quiz_id),
        )
        db.execute("DELETE FROM questions WHERE id_quiz = ?", (quiz_id,))
        for question in questions:
            db.execute(
                """
                INSERT INTO questions (id_quiz, texte, type, reponses_possibles, reponse_correcte, points)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    quiz_id,
                    question["texte"],
                    question["type"],
                    json.dumps(question["reponses_possibles"], ensure_ascii=True),
                    question["reponse_correcte"],
                    question["points"],
                ),
            )
        db.commit()
        clear_search_cache()
        flash("Quiz modifie.", "ok")
        return redirect(url_for("quizzes_list"))
    question_rows = db.execute(
        "SELECT texte, type, reponses_possibles, reponse_correcte, points FROM questions WHERE id_quiz = ? ORDER BY id",
        (quiz_id,),
    ).fetchall()
    normalized = []
    for row in question_rows:
        possibles = []
        if row["reponses_possibles"]:
            try:
                possibles = json.loads(row["reponses_possibles"])
            except json.JSONDecodeError:
                possibles = []
        normalized.append(
            {
                "texte": row["texte"],
                "type": row["type"],
                "reponses_possibles": possibles,
                "reponse_correcte": row["reponse_correcte"],
                "points": row["points"],
            }
        )
    return render_template(
        "quizzes_form.html",
        edit_quiz=quiz,
        questions_json=json.dumps(normalized, ensure_ascii=True, indent=2),
    )


@app.route("/quizzes/<int:quiz_id>/delete", methods=["GET", "POST"])
@login_required
def quizzes_delete(quiz_id: int):
    db = get_db()
    quiz = db.execute(
        "SELECT id, titre, id_createur FROM quizzes WHERE id = ? LIMIT 1", (quiz_id,)
    ).fetchone()
    if not quiz:
        abort(404)
    user = current_user()
    if not can_manage_quiz(quiz, user):
        abort(403)
    if request.method == "POST":
        if request.form.get("confirm") != "yes":
            flash("Confirmation obligatoire.", "error")
            return render_template("quizzes_delete.html", quiz=quiz)
        db.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
        db.commit()
        clear_search_cache()
        flash("Quiz supprime.", "ok")
        return redirect(url_for("quizzes_list"))
    return render_template("quizzes_delete.html", quiz=quiz)


@app.route("/quizzes/<int:quiz_id>")
def quiz_play(quiz_id: int):
    db = get_db()
    quiz = db.execute(
        """
        SELECT q.id, q.titre, q.description, q.id_createur, q.est_publique
        FROM quizzes q
        WHERE q.id = ? LIMIT 1
        """,
        (quiz_id,),
    ).fetchone()
    if not quiz:
        abort(404)
    user = current_user()
    if not quiz["est_publique"] and not can_manage_quiz(quiz, user):
        abort(403)
    questions = db.execute(
        "SELECT id, texte, type, reponses_possibles, points FROM questions WHERE id_quiz = ? ORDER BY id",
        (quiz_id,),
    ).fetchall()
    parsed_questions = []
    for row in questions:
        choices = []
        if row["type"] == "QCM" and row["reponses_possibles"]:
            try:
                choices = json.loads(row["reponses_possibles"])
            except json.JSONDecodeError:
                choices = []
        parsed_questions.append(
            {
                "id": row["id"],
                "texte": row["texte"],
                "type": row["type"],
                "points": row["points"],
                "choices": choices,
            }
        )
    leaderboard = db.execute(
        """
        SELECT u.username, s.score
        FROM sessions_quiz s
        JOIN users u ON u.id = s.id_utilisateur
        WHERE s.id_quiz = ?
        ORDER BY s.score DESC, s.created_at DESC
        LIMIT 20
        """,
        (quiz_id,),
    ).fetchall()
    return render_template("quiz_play.html", quiz=quiz, questions=parsed_questions, leaderboard=leaderboard)


@app.route("/quizzes/<int:quiz_id>/submit", methods=["POST"])
def quiz_submit(quiz_id: int):
    db = get_db()
    quiz = db.execute(
        "SELECT id, est_publique, id_createur FROM quizzes WHERE id = ? LIMIT 1", (quiz_id,)
    ).fetchone()
    if not quiz:
        abort(404)
    user = current_user()
    if not quiz["est_publique"] and not can_manage_quiz(quiz, user):
        abort(403)
    question_rows = db.execute(
        "SELECT id, type, reponse_correcte, points FROM questions WHERE id_quiz = ? ORDER BY id",
        (quiz_id,),
    ).fetchall()
    score = 0
    for row in question_rows:
        answer = request.form.get(f"q_{row['id']}", "").strip()
        if answer and answer.lower() == row["reponse_correcte"].strip().lower():
            score += row["points"]
    if user:
        db.execute(
            "INSERT INTO sessions_quiz (id_utilisateur, id_quiz, score) VALUES (?, ?, ?)",
            (user["id"], quiz_id, score),
        )
        db.commit()
    flash(f"Score final: {score}", "ok")
    return redirect(url_for("quiz_play", quiz_id=quiz_id))


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8000, debug=False)
