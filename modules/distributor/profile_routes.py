from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import re

# ── Blueprint ─────────────────────────────────────────────────────────────────
distributor_profile_bp = Blueprint(
    'distributor_profile_bp',
    __name__,
    template_folder='templates',
    static_folder='static'
)

# Injected from app.py (same pattern as all other routes in this project)
mysql  = None
bcrypt = None

# ── Config ────────────────────────────────────────────────────────────────────
UPLOAD_FOLDER  = 'static/uploads/distributors'
ALLOWED_EXT    = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_MB = 5


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def get_distributor(distributor_id):
    """Fetch distributor row as a dict."""
    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT * FROM distributor WHERE distributor_id = %s", (distributor_id,)
    )
    cols   = [d[0] for d in cursor.description]
    result = cursor.fetchone()
    cursor.close()
    return dict(zip(cols, result)) if result else None


# ── View Profile ──────────────────────────────────────────────────────────────
@distributor_profile_bp.route('/profile')
def view_profile():
    if 'distributor_id' not in session:
        flash('Please log in to view your profile.', 'error')
        return redirect(url_for('distributor_bp.login'))

    distributor = get_distributor(session['distributor_id'])
    if not distributor:
        flash('Profile not found.', 'error')
        return redirect(url_for('distributor_bp.dashboard'))

    return render_template('profile.html',
                           distributor=distributor, edit_mode=False)


# ── Edit Profile ──────────────────────────────────────────────────────────────
@distributor_profile_bp.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'distributor_id' not in session:
        flash('Please log in to edit your profile.', 'error')
        return redirect(url_for('distributor_bp.login'))

    distributor = get_distributor(session['distributor_id'])
    if not distributor:
        flash('Profile not found.', 'error')
        return redirect(url_for('distributor_bp.dashboard'))

    if request.method == 'POST':
        distributor_name = request.form.get('distributor_name', '').strip()
        owner_name       = request.form.get('owner_name', '').strip()
        district         = request.form.get('district', '').strip()
        province         = request.form.get('province', '').strip()
        contact_no       = request.form.get('contact_no', '').strip()
        address          = request.form.get('address', '').strip()

        # ── Validation ──
        errors = []
        if not distributor_name:
            errors.append('Business name is required.')
        if contact_no and not re.match(r'^[\d\s\+\-\(\)]{7,20}$', contact_no):
            errors.append('Contact number format is invalid.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('profile.html',      # ✅ fixed path
                                   distributor=distributor, edit_mode=True)

        # ── Image upload ──
        image_filename = distributor.get('distributor_image')
        file = request.files.get('distributor_image')
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Invalid image type. Allowed: PNG, JPG, JPEG, GIF, WEBP.', 'error')
                return render_template('profile.html',  # ✅ fixed path
                                       distributor=distributor, edit_mode=True)

            file.seek(0, os.SEEK_END)
            size_mb = file.tell() / (1024 * 1024)
            file.seek(0)
            if size_mb > MAX_CONTENT_MB:
                flash(f'Image must be under {MAX_CONTENT_MB}MB.', 'error')
                return render_template('profile.html',  # ✅ fixed path
                                       distributor=distributor, edit_mode=True)

            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            image_filename = secure_filename(
                f"dist_{session['distributor_id']}_{file.filename}"
            )
            file.save(os.path.join(UPLOAD_FOLDER, image_filename))

        # ── Update DB ──
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE distributor
            SET distributor_name  = %s,
                owner_name        = %s,
                district          = %s,
                province          = %s,
                contact_no        = %s,
                address           = %s,
                distributor_image = %s
            WHERE distributor_id  = %s
        """, (
            distributor_name, owner_name, district,
            province, contact_no, address,
            image_filename, session['distributor_id']
        ))
        mysql.connection.commit()
        cursor.close()

        session['distributor_name'] = distributor_name
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('distributor_profile_bp.view_profile'))

    return render_template('profile.html',              # ✅ fixed path
                           distributor=distributor, edit_mode=True)


# ── Change Password ───────────────────────────────────────────────────────────
@distributor_profile_bp.route('/profile/change-password', methods=['POST'])
def change_password():
    if 'distributor_id' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('distributor_bp.login'))

    current_password = request.form.get('current_password', '')
    new_password     = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    cursor = mysql.connection.cursor()
    cursor.execute(
        "SELECT password FROM distributor WHERE distributor_id = %s",
        (session['distributor_id'],)
    )
    row = cursor.fetchone()
    cursor.close()

    if not row:
        flash('Account not found.', 'error')
        return redirect(url_for('distributor_profile_bp.view_profile'))

    if not check_password_hash(row[0], current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('distributor_profile_bp.view_profile'))

    if len(new_password) < 8:
        flash('New password must be at least 8 characters.', 'error')
        return redirect(url_for('distributor_profile_bp.view_profile'))

    if new_password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('distributor_profile_bp.view_profile'))

    hashed = generate_password_hash(new_password)
    cursor = mysql.connection.cursor()
    cursor.execute(
        "UPDATE distributor SET password = %s WHERE distributor_id = %s",
        (hashed, session['distributor_id'])
    )
    mysql.connection.commit()
    cursor.close()

    flash('Password changed successfully!', 'success')
    return redirect(url_for('distributor_profile_bp.view_profile'))