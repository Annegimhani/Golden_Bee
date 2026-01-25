from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
import os

# These will be injected from app.py
mysql = None
bcrypt = None

# Define the Blueprint for distributor module
distributor_bp = Blueprint(
    "distributor_bp",
    __name__,
    template_folder="templates",  # Points to modules/admin/templates
    static_folder="static",       # Points to modules/admin/static
    static_url_path='/distributor_static'
)

# Distributor management route (view all distributors)
@distributor_bp.route("/manage_distributors", methods=["GET"])
def manage_distributors():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM distributor")
    distributors = cur.fetchall()
    cur.close()
    return render_template("manage_distributors.html", distributors=distributors)

# Add distributor route
@distributor_bp.route("/add_distributor", methods=["GET", "POST"])
def add_distributor():
    if request.method == "POST":
        distributor_name = request.form["distributor_name"]
        district = request.form["district"]
        province = request.form["province"]
        owner_name = request.form["owner_name"]
        contact_no = request.form["contact_no"]
        address = request.form["address"]
        email = request.form["email"]
        password = request.form["password"]
        
        # Handle image upload
        image = request.files.get("distributor_image")
        if image:
            image_filename = secure_filename(image.filename)
            image.save(os.path.join('static/images', image_filename))  # Save image to static/images folder
        else:
            image_filename = None  # No image uploaded

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                "INSERT INTO distributor (distributor_name, district, province, owner_name, contact_no, address, email, password, distributor_image) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (distributor_name, district, province, owner_name, contact_no, address, email, password, image_filename)
            )
            mysql.connection.commit()
            flash("Distributor added successfully", "success")
            return redirect(url_for("distributor_bp.manage_distributors"))
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error: {e}", "error")
        finally:
            cur.close()

    return render_template("add_distributor.html")

# Update distributor route
@distributor_bp.route("/update_distributor/<int:distributor_id>", methods=["GET", "POST"])
def update_distributor(distributor_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM distributor WHERE distributor_id = %s", (distributor_id,))
    distributor = cur.fetchone()
    cur.close()

    if request.method == "POST":
        distributor_name = request.form["distributor_name"]
        district = request.form["district"]
        province = request.form["province"]
        owner_name = request.form["owner_name"]
        contact_no = request.form["contact_no"]
        address = request.form["address"]
        email = request.form["email"]
        password = request.form["password"]

        # Handle image upload
        image = request.files.get("distributor_image")
        if image:
            image_filename = secure_filename(image.filename)
            image.save(os.path.join('static/images', image_filename))  # Save image to static/images folder
        else:
            image_filename = distributor[9]  # Keep the existing image if no new one is uploaded

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                "UPDATE distributor SET distributor_name=%s, district=%s, province=%s, owner_name=%s, contact_no=%s, address=%s, email=%s, password=%s, distributor_image=%s WHERE distributor_id=%s",
                (distributor_name, district, province, owner_name, contact_no, address, email, password, image_filename, distributor_id)
            )
            mysql.connection.commit()
            flash("Distributor updated successfully", "success")
            return redirect(url_for("distributor_bp.manage_distributors"))
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error: {e}", "error")
        finally:
            cur.close()

    return render_template("update_distributor.html", distributor=distributor)

# Delete distributor route
@distributor_bp.route("/delete_distributor/<int:distributor_id>", methods=["GET"])
def delete_distributor(distributor_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("DELETE FROM distributor WHERE distributor_id = %s", (distributor_id,))
        mysql.connection.commit()
        flash("Distributor deleted successfully", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error: {e}", "error")
    finally:
        cur.close()

    return redirect(url_for("distributor_bp.manage_distributors"))
