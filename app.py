from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import Flask, current_app, flash, g, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "instance" / "reminders.sqlite3"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        DATABASE=str(DATABASE_PATH),
    )

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        init_db()

    @app.teardown_appcontext
    def close_db(_error: Exception | None) -> None:
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    @app.route("/", methods=["GET", "POST"])
    def home():
        if request.method == "POST":
            action = request.form.get("action", "")

            if action == "create_category":
                name = request.form.get("name", "").strip()
                budget_text = request.form.get("budget", "").strip()

                if not name:
                    flash("List name is required.", "error")
                    return redirect(url_for("home"))

                try:
                    budget = float(budget_text)
                except ValueError:
                    flash("Budget must be a number.", "error")
                    return redirect(url_for("home"))

                with get_db() as db:
                    db.execute(
                        "INSERT INTO categories (name, budget) VALUES (?, ?)",
                        (name, budget),
                    )
                    db.commit()

                flash("List created.", "success")
                return redirect(url_for("home"))

            if action == "add_item":
                category_id_text = request.form.get("category_id", "").strip()
                title = request.form.get("title", "").strip()
                price_text = request.form.get("price", "").strip()

                if not category_id_text.isdigit():
                    flash("Pick a valid list.", "error")
                    return redirect(url_for("home"))

                category_id = int(category_id_text)
                if not title:
                    flash("Item name is required.", "error")
                    return redirect(url_for("home"))

                try:
                    price = float(price_text)
                except ValueError:
                    flash("Item price must be a number.", "error")
                    return redirect(url_for("home"))

                with get_db() as db:
                    db.execute(
                        "INSERT INTO items (category_id, name, price) VALUES (?, ?, ?)",
                        (category_id, title, price),
                    )
                    db.commit()

                flash("Item added.", "success")
                return redirect(url_for("home", open_category=category_id))

            if action == "update_category":
                category_id_text = request.form.get("category_id", "").strip()
                name = request.form.get("name", "").strip()
                budget_text = request.form.get("budget", "").strip()

                if not category_id_text.isdigit():
                    flash("Pick a valid list.", "error")
                    return redirect(url_for("home"))

                if not name:
                    flash("List name is required.", "error")
                    return redirect(url_for("home"))

                try:
                    budget = float(budget_text)
                except ValueError:
                    flash("Budget must be a number.", "error")
                    return redirect(url_for("home"))

                with get_db() as db:
                    result = db.execute(
                        "UPDATE categories SET name = ?, budget = ? WHERE id = ?",
                        (name, budget, int(category_id_text)),
                    )
                    db.commit()

                if result.rowcount == 0:
                    flash("List not found.", "error")
                else:
                    flash("List updated.", "success")
                return redirect(url_for("home", open_category=int(category_id_text)))

            if action == "delete_category":
                category_id_text = request.form.get("category_id", "").strip()

                if not category_id_text.isdigit():
                    flash("Pick a valid list.", "error")
                    return redirect(url_for("home"))

                with get_db() as db:
                    result = db.execute("DELETE FROM categories WHERE id = ?", (int(category_id_text),))
                    db.commit()

                if result.rowcount == 0:
                    flash("List not found.", "error")
                else:
                    flash("List deleted.", "success")
                return redirect(url_for("home"))

            if action == "reset_items":
                with get_db() as db:
                    db.execute("DELETE FROM items")
                    db.commit()

                flash("All list items cleared.", "success")
                return redirect(url_for("home"))

            flash("Unknown action.", "error")
            return redirect(url_for("home"))

        open_category = request.args.get("open_category", type=int)
        return render_template("home.html", categories=fetch_categories(), open_category=open_category)

    return app


def get_db() -> sqlite3.Connection:
    connection = g.get("db")
    if connection is None:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return connection


def init_db() -> None:
    with sqlite3.connect(DATABASE_PATH) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                budget REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            );
            """
        )

        category_columns = {row[1] for row in db.execute("PRAGMA table_info(categories)").fetchall()}
        if "budget" not in category_columns:
            db.execute("ALTER TABLE categories ADD COLUMN budget REAL NOT NULL DEFAULT 0")

        item_columns = {row[1] for row in db.execute("PRAGMA table_info(items)").fetchall()}
        if "name" not in item_columns:
            db.execute("ALTER TABLE items ADD COLUMN name TEXT")
        if "price" not in item_columns:
            db.execute("ALTER TABLE items ADD COLUMN price REAL NOT NULL DEFAULT 0")
        if "title" in item_columns:
            db.execute("UPDATE items SET name = COALESCE(name, title) WHERE name IS NULL")
        db.commit()


def fetch_categories() -> list[dict]:
    with sqlite3.connect(DATABASE_PATH) as db:
        db.row_factory = sqlite3.Row
        categories = db.execute(
            """
            SELECT id, name, budget
            FROM categories
            ORDER BY id DESC
            """
        ).fetchall()
        items = db.execute(
            """
            SELECT id, category_id, name, price
            FROM items
            ORDER BY id DESC
            """
        ).fetchall()

    items_by_category: dict[int, list[dict]] = {}
    spent_by_category: dict[int, float] = {}
    for item in items:
        items_by_category.setdefault(item["category_id"], []).append(dict(item))
        spent_by_category[item["category_id"]] = spent_by_category.get(item["category_id"], 0) + float(item["price"] or 0)

    return [
        {
            "id": category["id"],
            "name": category["name"],
            "items": items_by_category.get(category["id"], []),
            "item_count": len(items_by_category.get(category["id"], [])),
            "budget": float(category["budget"] or 0),
            "spent": spent_by_category.get(category["id"], 0),
            "utilization": (spent_by_category.get(category["id"], 0) / float(category["budget"] or 0)) if float(category["budget"] or 0) else 0,
            "remaining": float(category["budget"] or 0) - spent_by_category.get(category["id"], 0),
        }
        for category in categories
    ]
app = create_app()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)