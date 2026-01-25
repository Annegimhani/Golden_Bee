import MySQLdb
from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
import os

# These will be injected from app.py
mysql = None
bcrypt = None

# Initialize the blueprint for product management
product_mgmt_bp = Blueprint('product_mgmt', __name__, template_folder='templates', static_folder='static')

# Routes for managing products
@product_mgmt_bp.route('/manage_products')
def manage_products():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)  # Using DictCursor
    cur.execute("""
        SELECT p.product_id, p.product_name, c.category_name, p.unit_price, 
               p.variant_size, p.shelf_life_days, p.product_image
        FROM products p
        JOIN category c ON p.category_id = c.category_id
        ORDER BY p.product_id DESC
    """)
    products = cur.fetchall()
    cur.close()
    return render_template('manage_products.html', products=products)





@product_mgmt_bp.route('/add_product', methods=['GET', 'POST'])
def add_product():
    # Fetch categories from the database to populate the dropdown
    cur = mysql.connection.cursor()
    cur.execute("SELECT category_id, category_name FROM category")
    categories = cur.fetchall()
    cur.close()

    if request.method == 'POST':
        # Product information from form
        product_name = request.form.get('product_name')
        category_id = request.form.get('category_name')  # Get category_id from the form
        unit_price = request.form.get('unit_price')
        variant_size = request.form.get('variant_size')
        shelf_life_days = request.form.get('shelf_life_days')
        
        # Handle image upload
        image = request.files.get('product_image')
        if image and image.filename:
            # Create the directory if it doesn't exist
            image_dir = os.path.join('static', 'images', 'products')
            os.makedirs(image_dir, exist_ok=True)
            
            # Secure the image filename and save it
            image_filename = secure_filename(image.filename)
            image_path = os.path.join(image_dir, image_filename)
            image.save(image_path)
            image_filename = os.path.join('images', 'products', image_filename)

        # Insert product into the database
        cur = mysql.connection.cursor()
        try:
            cur.execute("""INSERT INTO products 
                (product_name, category_id, unit_price, variant_size, shelf_life_days, product_image)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (product_name, category_id, unit_price, variant_size, shelf_life_days, image_filename))
            mysql.connection.commit()
            flash("Product added successfully!", "success")
            return redirect(url_for('product_mgmt.manage_products'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error adding product: {str(e)}", "error")
        finally:
            cur.close()

    return render_template('add_product.html', categories=categories)


@product_mgmt_bp.route('/update_product/<int:product_id>', methods=['GET', 'POST'])
def update_product(product_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)  # Using DictCursor to get results as dictionaries
    
    # Fetch the product using the product_id
    cur.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
    product = cur.fetchone()
    cur.close()

    if not product:
        flash("Product not found", "error")
        return redirect(url_for('product_mgmt.manage_products'))

    # Fetch categories to populate the category dropdown
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT category_id, category_name FROM category")
    categories = cur.fetchall()
    cur.close()

    if request.method == 'POST':
        # Handle form submission to update the product
        product_name = request.form.get('product_name')
        category_id = request.form.get('category_name')  # Ensure category_id is passed
        unit_price = request.form.get('unit_price')
        variant_size = request.form.get('variant_size')
        shelf_life_days = request.form.get('shelf_life_days')
        
        # Handle image upload
        image = request.files.get('product_image')
        if image and image.filename:
            image_filename = secure_filename(image.filename)
            image_path = os.path.join('static', 'images', 'products', image_filename)
            image.save(image_path)
            image_filename = os.path.join('images', 'products', image_filename)
        else:
            image_filename = product['product_image']  # Retain the existing image if no new image is uploaded

        # Update the product in the database
        cur = mysql.connection.cursor()
        try:
            cur.execute("""UPDATE products SET 
                product_name = %s, category_id = %s, unit_price = %s, 
                variant_size = %s, shelf_life_days = %s, product_image = %s
                WHERE product_id = %s""",
                (product_name, category_id, unit_price, variant_size, shelf_life_days, image_filename, product_id))
            mysql.connection.commit()
            flash("Product updated successfully!", "success")
            return redirect(url_for('product_mgmt.manage_products'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error updating product: {str(e)}", "error")
        finally:
            cur.close()

    return render_template('update_product.html', product=product, categories=categories)


@product_mgmt_bp.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    cur = mysql.connection.cursor()
    try:
        cur.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        mysql.connection.commit()
        flash("Product deleted successfully", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error deleting product: {str(e)}", "error")
    finally:
        cur.close()

    return redirect(url_for('product_mgmt.manage_products'))
