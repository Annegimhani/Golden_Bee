from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app

# These will be injected from app.py
mysql = None
bcrypt = None

# IMPORTANT: blueprint name must be "admin" because you use url_for("admin.admin_login")
admin_bp = Blueprint(
    "admin", 
    __name__, 
    template_folder="templates",  # Points to modules/admin/templates
    static_folder="static",       # Points to modules/admin/static
    static_url_path='/admin_static'
)

# Home route
@admin_bp.route("/")
def home():
    return redirect(url_for("admin.admin_login"))

# Registration route
@admin_bp.route("/register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not username or not password:
            flash("Username and password required.", "error")
            return redirect(url_for("admin.admin_register"))

        hashed = bcrypt.generate_password_hash(password).decode("utf-8")

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                "INSERT INTO admin_user (username, password) VALUES (%s, %s)",
                (username, hashed),
            )
            mysql.connection.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("admin.admin_login"))
        except Exception as exc:
            current_app.logger.exception("Registration error: %s", exc)
            mysql.connection.rollback()
            flash("Username already exists or DB error.", "error")
            return redirect(url_for("admin.admin_register"))
        finally:
            cur.close()

    return render_template("register.html", active_page="register")

# Login route
@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT id, username, password FROM admin_user WHERE username = %s",
            (username,),
        )
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user[2], password):
            session["user_id"] = user[0]
            session["username"] = user[1]
            flash("Logged in!", "success")
            return redirect(url_for("admin.admin_dashboard"))

        flash("Invalid username or password.", "error")
        return redirect(url_for("admin.admin_login"))

    return render_template("login.html", active_page="login")

# Dashboard route
@admin_bp.route("/dashboard")
def admin_dashboard():
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("admin.admin_login"))

    return render_template("dashboard.html", username=session.get("username"))

# Logout route
@admin_bp.route("/logout")
def admin_logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("admin.admin_login"))
