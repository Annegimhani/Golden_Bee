from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt
from config.db_config import init_db

# Initialize MySQL and Bcrypt (inject from app.py)
bcrypt = Bcrypt()
mysql = None

# Create Blueprint for distributor
distributor_bp = Blueprint(
    'distributor', 
    __name__, 
    template_folder='templates',  # Points to modules/distributor/templates
    static_folder='static',       # Points to modules/distributor/static
    static_url_path='/distributor_static'  # This defines the URL for static files
)

# Home route
@distributor_bp.route("/")
def home():
    return redirect(url_for("distributor.distributor_login"))

# Distributor login route
@distributor_bp.route("/login", methods=["GET", "POST"])
def distributor_login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        # Connect to MySQL database
        cur = mysql.connection.cursor()
        
        # Fetch user by email
        cur.execute(
            "SELECT distributor_id, distributor_name, email, password FROM distributor WHERE email = %s",
            (email,),
        )
        user = cur.fetchone()
        cur.close()

        # Check if user exists and password is correct
        if user and bcrypt.check_password_hash(user[3], password):
            # Store session information
            session["distributor_id"] = user[0]
            session["distributor_name"] = user[1]
            session["distributor_email"] = user[2]
            flash("Logged in successfully!", "success")
            return redirect(url_for("distributor.distributor_dashboard"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("distributor.distributor_login"))

    return render_template("distributor_login.html", active_page="login")

# Distributor dashboard route
@distributor_bp.route("/dashboard")
def distributor_dashboard():
    if "distributor_id" not in session:
        flash("Please log in first", "error")
        return redirect(url_for("distributor.distributor_login"))

    return render_template("distributor_dashboard.html", username=session.get("distributor_name"))

# Distributor logout route
@distributor_bp.route("/logout")
def distributor_logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("distributor.distributor_login"))
