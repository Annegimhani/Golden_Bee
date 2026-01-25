from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os
from MySQLdb.cursors import DictCursor  # Make sure to import DictCursor

# These will be injected from app.py
mysql = None
bcrypt = None

# Define the Blueprint for category management module
category_mgmt_bp = Blueprint(
    "category_mgmt",  # Blueprint name
    __name__,
    template_folder="templates",  # Points to modules/admin/templates
    static_folder="static",       # Points to modules/admin/static
    static_url_path="/category_static"  # URL path for static files
)

# Route to manage all categories
@category_mgmt_bp.route("/manage_categories", methods=["GET"])
def manage_categories():
    cur = mysql.connection.cursor(DictCursor)  # Use DictCursor to fetch results as dictionaries
    cur.execute("SELECT * FROM category ORDER BY category_id DESC")
    categories = cur.fetchall()  # Get all categories as dictionaries
    cur.close()
    return render_template("manage_categories.html", categories=categories)

# Route to add a new category
@category_mgmt_bp.route("/add_category", methods=["GET", "POST"])
def add_category():
    if request.method == "POST":
        category_name = request.form.get("category_name", "").strip()
        description = request.form.get("description", "").strip()

        # Validate required fields
        if not all([category_name, description]):
            flash("Both Category Name and Description are required.", "error")
            return redirect(url_for("category_mgmt.add_category"))

        # Insert category into the database
        cur = mysql.connection.cursor()
        try:
            cur.execute(
                """INSERT INTO category (category_name, description) VALUES (%s, %s)""",
                (category_name, description)
            )
            mysql.connection.commit()
            flash("Category added successfully", "success")
            return redirect(url_for("category_mgmt.manage_categories"))
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error adding category: {str(e)}", "error")
        finally:
            cur.close()

    return render_template("add_category.html")

# Route to update an existing category
@category_mgmt_bp.route("/update_category/<int:category_id>", methods=["GET", "POST"])
def update_category(category_id):
    cur = mysql.connection.cursor(DictCursor)  # Use DictCursor to fetch results as dictionaries
    cur.execute("SELECT * FROM category WHERE category_id = %s", (category_id,))
    category = cur.fetchone()  # Get category data
    cur.close()

    if not category:
        flash("Category not found", "error")
        return redirect(url_for("category_mgmt.manage_categories"))

    if request.method == "POST":
        category_name = request.form.get("category_name", "").strip()
        description = request.form.get("description", "").strip()

        # Validate required fields
        if not all([category_name, description]):
            flash("Both Category Name and Description are required.", "error")
            return redirect(url_for("category_mgmt.update_category", category_id=category_id))

        # Update the category in the database
        cur = mysql.connection.cursor()
        try:
            cur.execute(
                """UPDATE category SET category_name = %s, description = %s WHERE category_id = %s""",
                (category_name, description, category_id)
            )
            mysql.connection.commit()
            flash("Category updated successfully", "success")
            return redirect(url_for("category_mgmt.manage_categories"))
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error updating category: {str(e)}", "error")
        finally:
            cur.close()

    return render_template("update_category.html", category=category)

# Route to delete a category
@category_mgmt_bp.route("/delete_category/<int:category_id>", methods=["GET"])
def delete_category(category_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("DELETE FROM category WHERE category_id = %s", (category_id,))
        mysql.connection.commit()
        flash("Category deleted successfully", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error deleting category: {str(e)}", "error")
    finally:
        cur.close()

    return redirect(url_for("category_mgmt.manage_categories"))
