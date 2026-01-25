from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt
from config.db_config import init_db

# Initialize Bcrypt and MySQL (same as app.py)
bcrypt = Bcrypt()
mysql = None

# Create Blueprint for distributor
distributor_bp = Blueprint('distributor_bp', __name__)

# Distributor login route
@distributor_bp.route("/login", methods=["GET", "POST"])
def distributor_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, username, password FROM distributor_user WHERE username = %s",
            (username,),
        )
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user[2], password):
            session["distributor_id"] = user[0]
            session["distributor_username"] = user[1]
            flash("Logged in successfully!", "success")
            return redirect(url_for("distributor_bp.distributor_dashboard"))

        flash("Invalid username or password", "error")
        return redirect(url_for("distributor_bp.distributor_login"))

    return render_template("distributor/login.html", active_page="login")


# Distributor dashboard route
@distributor_bp.route("/dashboard")
def distributor_dashboard():
    if "distributor_id" not in session:
        flash("Please log in first", "error")
        return redirect(url_for("distributor_bp.distributor_login"))

    return render_template("distributor/dashboard.html", username=session.get("distributor_username"))


# Distributor logout route
@distributor_bp.route("/logout")
def distributor_logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("distributor_bp.distributor_login"))
