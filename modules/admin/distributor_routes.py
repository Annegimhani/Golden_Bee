from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os

# These will be injected from app.py
mysql = None
bcrypt = None

# Define the Blueprint for distributor management module
distributor_mgmt_bp = Blueprint(
    "distributor_mgmt",  # Blueprint name
    __name__,
    template_folder="templates",  # Points to modules/admin/templates
    static_folder="static",       # Points to modules/admin/static
    static_url_path="/distributor_static"  # URL path for static files
)

# Distributor management route (view all distributors)
@distributor_mgmt_bp.route("/manage_distributors", methods=["GET"])
def manage_distributors():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM distributor ORDER BY distributor_id DESC")
    distributors = cur.fetchall()
    cur.close()
    return render_template("manage_distributors.html", distributors=distributors)

# Add distributor route
@distributor_mgmt_bp.route("/add_distributor", methods=["GET", "POST"])
def add_distributor():
    if request.method == "POST":
        distributor_name = request.form.get("distributor_name", "").strip()
        district = request.form.get("district", "").strip()
        province = request.form.get("province", "").strip()
        owner_name = request.form.get("owner_name", "").strip()
        contact_no = request.form.get("contact_no", "").strip()
        address = request.form.get("address", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        # Validate required fields
        if not all([distributor_name, district, province, owner_name, contact_no, email, password]):
            flash("All fields except address are required.", "error")
            return redirect(url_for("distributor_mgmt_routes.add_distributor"))
        
        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Handle image upload
        image_filename = None
        image = request.files.get("distributor_image")
        if image and image.filename:
            # Create images directory if it doesn't exist
            image_dir = os.path.join('static', 'images', 'distributors')
            os.makedirs(image_dir, exist_ok=True)
            
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(image_dir, image_filename)
            image.save(image_path)
            # Store relative path
            image_filename = os.path.join('images', 'distributors', image_filename)

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                """INSERT INTO distributor 
                (distributor_name, district, province, owner_name, contact_no, address, email, password, distributor_image) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (distributor_name, district, province, owner_name, contact_no, address, email, hashed_password, image_filename)
            )
            mysql.connection.commit()
            flash("Distributor added successfully", "success")
            return redirect(url_for("distributor_mgmt_routes.manage_distributors"))
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error adding distributor: {str(e)}", "error")
        finally:
            cur.close()

    return render_template("add_distributor.html")

# Update distributor route
@distributor_mgmt_bp.route("/update_distributor/<int:distributor_id>", methods=["GET", "POST"])
def update_distributor(distributor_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM distributor WHERE distributor_id = %s", (distributor_id,))
    distributor = cur.fetchone()
    cur.close()

    if not distributor:
        flash("Distributor not found", "error")
        return redirect(url_for("distributor_mgmt_routes.manage_distributors"))

    if request.method == "POST":
        distributor_name = request.form.get("distributor_name", "").strip()
        district = request.form.get("district", "").strip()
        province = request.form.get("province", "").strip()
        owner_name = request.form.get("owner_name", "").strip()
        contact_no = request.form.get("contact_no", "").strip()
        address = request.form.get("address", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Handle password update (only if new password provided)
        if password:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        else:
            # Keep existing password
            hashed_password = distributor[8]  # Assuming password is at index 8

        # Handle image upload
        image_filename = distributor[9] if distributor[9] else None  # Existing image
        image = request.files.get("distributor_image")
        if image and image.filename:
            # Create images directory if it doesn't exist
            image_dir = os.path.join('static', 'images', 'distributors')
            os.makedirs(image_dir, exist_ok=True)
            
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(image_dir, image_filename)
            image.save(image_path)
            # Store relative path
            image_filename = os.path.join('images', 'distributors', image_filename)

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                """UPDATE distributor SET 
                distributor_name=%s, district=%s, province=%s, owner_name=%s, 
                contact_no=%s, address=%s, email=%s, password=%s, distributor_image=%s 
                WHERE distributor_id=%s""",
                (distributor_name, district, province, owner_name, contact_no, 
                 address, email, hashed_password, image_filename, distributor_id)
            )
            mysql.connection.commit()
            flash("Distributor updated successfully", "success")
            return redirect(url_for("distributor_mgmt_routes.manage_distributors"))
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error updating distributor: {str(e)}", "error")
        finally:
            cur.close()

    return render_template("update_distributor.html", distributor=distributor)

# Delete distributor route
@distributor_mgmt_bp.route("/delete_distributor/<int:distributor_id>", methods=["GET"])
def delete_distributor(distributor_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("DELETE FROM distributor WHERE distributor_id = %s", (distributor_id,))
        mysql.connection.commit()
        flash("Distributor deleted successfully", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error deleting distributor: {str(e)}", "error")
    finally:
        cur.close()

    return redirect(url_for("distributor_mgmt_routes.manage_distributors"))
