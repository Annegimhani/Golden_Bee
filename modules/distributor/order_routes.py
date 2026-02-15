# File: order_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import MySQLdb

# These will be injected from app.py
bcrypt = None
mysql = None

# Create Blueprint for distributor order management with original name
distributor_order_bp = Blueprint(
    'distributor_order_bp', 
    __name__, 
    template_folder='templates',
    static_folder='static',
    static_url_path='/distributor_static'
)

@distributor_order_bp.route('/manage_orders')
def manage_orders():
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        flash("Please log in first", "error")
        return redirect(url_for('distributor_order_bp.distributor_login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetch orders with aggregated quantity information
    cur.execute("""
        SELECT 
            o.order_id,
            o.order_date,
            o.status,
            o.total_amount,
            COUNT(oi.order_item_id) as item_count,
            COALESCE(SUM(oi.quantity), 0) as total_quantity,
            GROUP_CONCAT(
                CONCAT(oi.product_name, ' (Qty: ', oi.quantity, ')')
                SEPARATOR ', '
            ) as products_with_qty,
            GROUP_CONCAT(oi.product_name SEPARATOR ', ') as products,
            GROUP_CONCAT(oi.quantity SEPARATOR ', ') as quantities
        FROM orders o
        LEFT JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.distributor_id = %s
        GROUP BY o.order_id
        ORDER BY o.order_date DESC
    """, (distributor_id,))
    
    orders = cur.fetchall()
    cur.close()

    return render_template('manage_orders.html', orders=orders)

# Route to add a new order
@distributor_order_bp.route('/add_order', methods=["GET", "POST"])
def add_order():
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        flash("Please log in first", "error")
        return redirect(url_for('distributor_order_bp.distributor_login'))

    if request.method == "POST":
        # Get form data
        category_id = request.form.get("category_id")
        product_id = request.form.get("product_id")
        quantity = int(request.form.get("quantity", 1))
        variant_size = request.form.get("variant_size", "")
        
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        try:
            # 1. Get product price
            cur.execute("""
                SELECT unit_price, product_name FROM products 
                WHERE product_id = %s
            """, (product_id,))
            product = cur.fetchone()
            
            if not product:
                flash("Product not found", "error")
                return redirect(url_for('distributor_order_bp.add_order'))
            
            unit_price = product['unit_price']
            product_name = product['product_name']
            subtotal = unit_price * quantity
            
            # 2. Get category name
            cur.execute("""
                SELECT category_name FROM category 
                WHERE category_id = %s
            """, (category_id,))
            category = cur.fetchone()
            category_name = category['category_name'] if category else "Uncategorized"
            
            # 3. Create order with 'requested' status
            cur.execute("""
                INSERT INTO orders (distributor_id, order_date, status, total_amount)
                VALUES (%s, NOW(), 'requested', %s)
            """, (distributor_id, subtotal))
            
            order_id = cur.lastrowid
            
            # 4. Insert into order_items
            cur.execute("""
                INSERT INTO order_items 
                (order_id, product_id, category_id, product_name, category_name, 
                 unit_price, variant_size, quantity, subtotal)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (order_id, product_id, category_id, product_name, 
                  category_name, unit_price, variant_size, quantity, subtotal))
            
            mysql.connection.commit()
            flash("Order requested successfully!", "success")
            return redirect(url_for('distributor_order_bp.manage_orders'))
            
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error placing order: {str(e)}", "error")
            return redirect(url_for('distributor_order_bp.add_order'))
        finally:
            cur.close()

    # GET request - show form
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT category_id, category_name FROM category ORDER BY category_name")
    categories = cur.fetchall()
    cur.close()
    
    return render_template('add_order.html', categories=categories)

# Route to update an order
@distributor_order_bp.route('/update_order/<int:order_id>', methods=["GET", "POST"])
def update_order(order_id):
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        flash("Please log in first", "error")
        return redirect(url_for('distributor_order_bp.distributor_login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Get order and check if it can be updated (only requested orders)
    cur.execute("""
        SELECT * FROM orders 
        WHERE order_id = %s AND distributor_id = %s AND status = 'requested'
    """, (order_id, distributor_id))
    order = cur.fetchone()
    
    if not order:
        flash("Order cannot be updated or not found", "error")
        cur.close()
        return redirect(url_for('distributor_order_bp.manage_orders'))

    if request.method == "POST":
        # Get form data
        category_id = request.form.get("category_id")
        product_id = request.form.get("product_id")
        quantity = int(request.form.get("quantity", 1))
        variant_size = request.form.get("variant_size", "")
        
        try:
            # 1. Get product price
            cur.execute("""
                SELECT unit_price, product_name FROM products 
                WHERE product_id = %s
            """, (product_id,))
            product = cur.fetchone()
            
            if not product:
                flash("Product not found", "error")
                return redirect(url_for('distributor_order_bp.update_order', order_id=order_id))
            
            unit_price = product['unit_price']
            product_name = product['product_name']
            subtotal = unit_price * quantity
            
            # 2. Get category name
            cur.execute("""
                SELECT category_name FROM category 
                WHERE category_id = %s
            """, (category_id,))
            category = cur.fetchone()
            category_name = category['category_name'] if category else "Uncategorized"
            
            # 3. Update order total
            cur.execute("""
                UPDATE orders 
                SET total_amount = %s 
                WHERE order_id = %s
            """, (subtotal, order_id))
            
            # 4. Update order item
            cur.execute("""
                UPDATE order_items 
                SET product_id = %s, 
                    category_id = %s, 
                    product_name = %s, 
                    category_name = %s, 
                    unit_price = %s, 
                    variant_size = %s,
                    quantity = %s, 
                    subtotal = %s
                WHERE order_id = %s
            """, (product_id, category_id, product_name, category_name, 
                  unit_price, variant_size, quantity, subtotal, order_id))
            
            mysql.connection.commit()
            flash("Order updated successfully!", "success")
            return redirect(url_for('distributor_order_bp.manage_orders'))
            
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error updating order: {str(e)}", "error")
            return redirect(url_for('distributor_order_bp.update_order', order_id=order_id))
        finally:
            cur.close()
    
    # GET request - show form
    # Get current order item details
    cur.execute("""
        SELECT * FROM order_items 
        WHERE order_id = %s
    """, (order_id,))
    order_item = cur.fetchone()
    
    # Get categories
    cur.execute("SELECT category_id, category_name FROM category ORDER BY category_name")
    categories = cur.fetchall()
    
    # Get current category products
    current_category_id = order_item['category_id'] if order_item else None
    products = []
    if current_category_id:
        cur.execute("""
            SELECT product_id, product_name, unit_price 
            FROM products 
            WHERE category_id = %s
        """, (current_category_id,))
        products = cur.fetchall()
    
    cur.close()
    
    return render_template('update_order.html', 
                         order=order, 
                         order_item=order_item, 
                         categories=categories, 
                         products=products)

# Route to cancel a requested order
@distributor_order_bp.route('/cancel_order/<int:order_id>', methods=["POST"])
def cancel_order(order_id):
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        flash("Please log in first", "error")
        return redirect(url_for('distributor_order_bp.distributor_login'))

    cur = mysql.connection.cursor()
    
    try:
        # Check if order belongs to distributor and is in 'requested' status
        cur.execute("""
            UPDATE orders 
            SET status = 'cancelled' 
            WHERE order_id = %s 
            AND distributor_id = %s 
            AND status = 'requested'
        """, (order_id, distributor_id))
        
        if cur.rowcount == 0:
            flash("Order cannot be cancelled or not found", "error")
        else:
            mysql.connection.commit()
            flash("Order cancelled successfully", "success")
            
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error cancelling order: {str(e)}", "error")
    finally:
        cur.close()

    return redirect(url_for('distributor_order_bp.manage_orders'))

# Route to view order details
@distributor_order_bp.route('/order_details/<int:order_id>')
def order_details(order_id):
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        flash("Please log in first", "error")
        return redirect(url_for('distributor_order_bp.distributor_login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Get order info
    cur.execute("""
        SELECT * FROM orders 
        WHERE order_id = %s AND distributor_id = %s
    """, (order_id, distributor_id))
    order = cur.fetchone()
    
    if not order:
        flash("Order not found", "error")
        return redirect(url_for('distributor_order_bp.manage_orders'))
    
    # Get order items
    cur.execute("""
        SELECT * FROM order_items 
        WHERE order_id = %s
    """, (order_id,))
    items = cur.fetchall()
    
    cur.close()
    
    return render_template('order_details.html', order=order, items=items)

# Route to get products based on selected category
@distributor_order_bp.route('/get_products/<category_id>', methods=['GET'])
def get_products(category_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT product_id, product_name, unit_price 
        FROM products 
        WHERE category_id = %s
    """, (category_id,))
    products = cur.fetchall()
    cur.close()
    
    return jsonify({'products': products})

# Route to get products for update form (different from get_products)
@distributor_order_bp.route('/get_products_for_update/<category_id>', methods=['GET'])
def get_products_for_update(category_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT product_id, product_name, unit_price 
        FROM products 
        WHERE category_id = %s
    """, (category_id,))
    products = cur.fetchall()
    cur.close()
    
    return jsonify({'products': products})

# Login route for distributor (if needed)
@distributor_order_bp.route('/login', methods=['GET', 'POST'])
def distributor_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM distributors WHERE email = %s", (email,))
        distributor = cur.fetchone()
        cur.close()
        
        if distributor and bcrypt.check_password_hash(distributor['password_hash'], password):
            session['distributor_id'] = distributor['distributor_id']
            session['distributor_name'] = distributor['name']
            flash('Login successful!', 'success')
            return redirect(url_for('distributor_order_bp.manage_orders'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')

# Logout route
@distributor_order_bp.route('/logout')
def distributor_logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('distributor_order_bp.distributor_login'))