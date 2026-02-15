from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt
from config.db_config import init_db

# Initialize MySQL and Bcrypt (inject from app.py)
bcrypt = Bcrypt()
mysql = None

# Create Blueprint for distributor
# IMPORTANT: The first parameter 'distributor_bp' is the blueprint name used in url_for()
distributor_bp = Blueprint(
    'distributor_bp',  # This is the name you use in url_for('distributor_bp.route_name')
    __name__, 
    template_folder='templates',
    static_folder='static',
    static_url_path='/distributor_static'
)

# Home route
@distributor_bp.route("/")
def home():
    return redirect(url_for("distributor_bp.login"))

# Distributor login route
@distributor_bp.route("/login", methods=["GET", "POST"])
def login():  # Changed from distributor_login to just login
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        cur = mysql.connection.cursor()
        
        cur.execute(
            "SELECT distributor_id, distributor_name, email, password FROM distributor WHERE email = %s",
            (email,),
        )
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user[3], password):
            session["distributor_id"] = user[0]
            session["distributor_name"] = user[1]
            session["distributor_email"] = user[2]
            flash("Logged in successfully!", "success")
            return redirect(url_for("distributor_bp.dashboard"))  # Changed here

        flash("Invalid email or password.", "error")
        return redirect(url_for("distributor_bp.login"))

    return render_template("distributor_login.html", active_page="login")

# Distributor dashboard route
@distributor_bp.route("/dashboard")
def dashboard():  # Changed from distributor_dashboard to just dashboard
    if "distributor_id" not in session:
        flash("Please log in first", "error")
        return redirect(url_for("distributor_bp.login"))

    return render_template("distributor_dashboard.html", username=session.get("distributor_name"))

# Browse products route
@distributor_bp.route("/browse")
def browse_products():
    """Show categories or all products for ordering"""
    if "distributor_id" not in session:
        flash("Please log in first", "error")
        return redirect(url_for("distributor_bp.login"))
    
    # Redirect to order management which has product browsing
    return redirect(url_for("distributor_order_bp.manage_orders"))

# Distributor logout route
@distributor_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("distributor_bp.login"))