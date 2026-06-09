from __future__ import annotations

import os
from flask import Flask, flash, redirect, render_template, request, url_for

from supabase import create_client, Client

from dotenv import load_dotenv
load_dotenv()

def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    # 🔥 Supabase connection
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment variables")

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # -------------------------
    # HOME ROUTE
    # -------------------------
    @app.route("/", methods=["GET", "POST"])
    def home():

        if request.method == "POST":
            action = request.form.get("action", "")

            # ---------------- CREATE CATEGORY ----------------
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

                supabase.table("categories").insert({
                    "name": name,
                    "budget": budget
                }).execute()

                flash("List created.", "success")
                return redirect(url_for("home"))

            # ---------------- ADD ITEM ----------------
            if action == "add_item":
                category_id = request.form.get("category_id", "").strip()
                title = request.form.get("title", "").strip()
                price_text = request.form.get("price", "").strip()

                if not category_id.isdigit():
                    flash("Pick a valid list.", "error")
                    return redirect(url_for("home"))

                if not title:
                    flash("Item name is required.", "error")
                    return redirect(url_for("home"))

                try:
                    price = float(price_text)
                except ValueError:
                    flash("Item price must be a number.", "error")
                    return redirect(url_for("home"))

                supabase.table("items").insert({
                    "category_id": int(category_id),
                    "name": title,
                    "price": price
                }).execute()

                flash("Item added.", "success")
                return redirect(url_for("home", open_category=category_id))

            # ---------------- UPDATE CATEGORY ----------------
            if action == "update_category":
                category_id = request.form.get("category_id", "").strip()
                name = request.form.get("name", "").strip()
                budget_text = request.form.get("budget", "").strip()

                if not category_id.isdigit():
                    flash("Invalid category.", "error")
                    return redirect(url_for("home"))

                try:
                    budget = float(budget_text)
                except ValueError:
                    flash("Budget must be a number.", "error")
                    return redirect(url_for("home"))

                res = supabase.table("categories") \
                    .update({"name": name, "budget": budget}) \
                    .eq("id", int(category_id)) \
                    .execute()

                if not res.data:
                    flash("List not found.", "error")
                else:
                    flash("List updated.", "success")

                return redirect(url_for("home", open_category=category_id))

            # ---------------- DELETE CATEGORY ----------------
            if action == "delete_category":
                category_id = request.form.get("category_id", "").strip()

                if not category_id.isdigit():
                    flash("Invalid category.", "error")
                    return redirect(url_for("home"))

                supabase.table("categories") \
                    .delete() \
                    .eq("id", int(category_id)) \
                    .execute()

                flash("List deleted.", "success")
                return redirect(url_for("home"))

            # ---------------- RESET ITEMS ----------------
            if action == "reset_items":
                supabase.table("items").delete().neq("id", 0).execute()
                flash("All items cleared.", "success")
                return redirect(url_for("home"))

            flash("Unknown action.", "error")
            return redirect(url_for("home"))

        # ---------------- GET DATA ----------------
        categories_res = supabase.table("categories").select("*").execute()
        items_res = supabase.table("items").select("*").execute()

        categories = categories_res.data or []
        items = items_res.data or []

        # ---------------- GROUP ITEMS ----------------
        items_by_category = {}
        spent_by_category = {}

        for item in items:
            cid = item["category_id"]
            items_by_category.setdefault(cid, []).append(item)
            spent_by_category[cid] = spent_by_category.get(cid, 0) + float(item["price"] or 0)

        # ---------------- BUILD RESPONSE ----------------
        enriched = []
        for c in categories:
            spent = spent_by_category.get(c["id"], 0)
            budget = float(c.get("budget") or 0)

            enriched.append({
                "id": c["id"],
                "name": c["name"],
                "budget": budget,
                "items": items_by_category.get(c["id"], []),
                "item_count": len(items_by_category.get(c["id"], [])),
                "spent": spent,
                "utilization": (spent / budget) if budget else 0,
                "remaining": budget - spent,
            })

        open_category = request.args.get("open_category", type=int)

        return render_template(
            "home.html",
            categories=enriched,
            open_category=open_category
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)