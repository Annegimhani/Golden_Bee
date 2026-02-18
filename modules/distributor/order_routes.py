# File: order_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import MySQLdb

# These will be injected from app.py
bcrypt = None
mysql = None

# Create Blueprint for distributor order management
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
        return redirect(url_for('distributor_bp.login'))

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

# NEW: Get unread message count
@distributor_order_bp.route('/unread_count')
def unread_count():
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        return jsonify({'count': 0})
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        # Count unread admin messages for this distributor
        cur.execute("""
            SELECT COUNT(*) as count
            FROM messages m
            JOIN orders o ON m.order_id = o.order_id
            WHERE o.distributor_id = %s 
            AND m.admin_id IS NOT NULL 
            AND m.is_read = 0
        """, (distributor_id,))
        
        result = cur.fetchone()
        count = result['count'] if result else 0
        
        return jsonify({'count': count})
        
    except Exception as e:
        return jsonify({'count': 0, 'error': str(e)})
    finally:
        cur.close()

# NEW: Get messages for an order
@distributor_order_bp.route('/get_messages/<int:order_id>')
def get_messages(order_id):
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Verify order belongs to distributor
    cur.execute("""
        SELECT order_id FROM orders 
        WHERE order_id = %s AND distributor_id = %s
    """, (order_id, distributor_id))
    
    if not cur.fetchone():
        cur.close()
        return jsonify({'error': 'Order not found'}), 404
    
    # Get all messages for this order
    cur.execute("""
        SELECT 
            message_id,
            order_id,
            distributor_id,
            admin_id,
            message,
            message_type,
            created_at,
            is_read
        FROM messages
        WHERE order_id = %s
        ORDER BY created_at ASC
    """, (order_id,))
    
    messages = cur.fetchall()
    cur.close()
    
    # Format messages for JSON
    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            'message_id': msg['message_id'],
            'message': msg['message'],
            'message_type': msg['message_type'],
            'created_at': msg['created_at'].strftime('%Y-%m-%d %H:%M:%S') if msg['created_at'] else '',
            'is_from_admin': msg['admin_id'] is not None,
            'is_read': msg['is_read']
        })
    
    return jsonify({'messages': formatted_messages})

# NEW: Send message
@distributor_order_bp.route('/send_message', methods=['POST'])
def send_message():
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.get_json()
    order_id = data.get('order_id')
    message = data.get('message', '').strip()
    
    if not order_id or not message:
        return jsonify({'error': 'Missing data'}), 400
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        # Verify order belongs to distributor
        cur.execute("""
            SELECT order_id FROM orders 
            WHERE order_id = %s AND distributor_id = %s
        """, (order_id, distributor_id))
        
        if not cur.fetchone():
            return jsonify({'error': 'Order not found'}), 404
        
        # Insert message
        cur.execute("""
            INSERT INTO messages 
            (order_id, distributor_id, message, message_type, created_at, is_read)
            VALUES (%s, %s, %s, 'question', NOW(), 0)
        """, (order_id, distributor_id, message))
        
        mysql.connection.commit()
        
        return jsonify({
            'success': True,
            'message': 'Message sent successfully'
        })
        
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()

# NEW: Mark messages as read
@distributor_order_bp.route('/mark_messages_read/<int:order_id>', methods=['POST'])
def mark_messages_read(order_id):
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    cur = mysql.connection.cursor()
    
    try:
        # Mark admin messages as read for this order
        cur.execute("""
            UPDATE messages 
            SET is_read = 1 
            WHERE order_id = %s 
            AND distributor_id = %s 
            AND admin_id IS NOT NULL
            AND is_read = 0
        """, (order_id, distributor_id))
        
        mysql.connection.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()

# Route to add a new order
@distributor_order_bp.route('/add_order', methods=["GET", "POST"])
def add_order():
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        flash("Please log in first", "error")
        return redirect(url_for('distributor_bp.login'))

    if request.method == "POST":
        category_id = request.form.get("category_id")
        product_id = request.form.get("product_id")
        quantity = int(request.form.get("quantity", 1))
        variant_size = request.form.get("variant_size", "")
        
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        try:
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
            
            cur.execute("""
                SELECT category_name FROM category 
                WHERE category_id = %s
            """, (category_id,))
            category = cur.fetchone()
            category_name = category['category_name'] if category else "Uncategorized"
            
            cur.execute("""
                INSERT INTO orders (distributor_id, order_date, status, total_amount)
                VALUES (%s, NOW(), 'pending', %s)
            """, (distributor_id, subtotal))
            
            order_id = cur.lastrowid
            
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
        return redirect(url_for('distributor_bp.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cur.execute("""
        SELECT * FROM orders 
        WHERE order_id = %s AND distributor_id = %s AND status = 'pending'
    """, (order_id, distributor_id))
    order = cur.fetchone()
    
    if not order:
        flash("Order cannot be updated or not found", "error")
        cur.close()
        return redirect(url_for('distributor_order_bp.manage_orders'))

    if request.method == "POST":
        category_id = request.form.get("category_id")
        product_id = request.form.get("product_id")
        quantity = int(request.form.get("quantity", 1))
        variant_size = request.form.get("variant_size", "")
        
        try:
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
            
            cur.execute("""
                SELECT category_name FROM category 
                WHERE category_id = %s
            """, (category_id,))
            category = cur.fetchone()
            category_name = category['category_name'] if category else "Uncategorized"
            
            cur.execute("""
                UPDATE orders 
                SET total_amount = %s 
                WHERE order_id = %s
            """, (subtotal, order_id))
            
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
    
    cur.execute("""
        SELECT * FROM order_items 
        WHERE order_id = %s
    """, (order_id,))
    order_item = cur.fetchone()
    
    cur.execute("SELECT category_id, category_name FROM category ORDER BY category_name")
    categories = cur.fetchall()
    
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

# Route to cancel an order
@distributor_order_bp.route('/cancel_order/<int:order_id>', methods=["POST"])
def cancel_order(order_id):
    distributor_id = session.get('distributor_id')
    if not distributor_id:
        flash("Please log in first", "error")
        return redirect(url_for('distributor_bp.login'))

    cur = mysql.connection.cursor()
    
    try:
        cur.execute("""
            UPDATE orders 
            SET status = 'cancelled' 
            WHERE order_id = %s 
            AND distributor_id = %s 
            AND status = 'pending'
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
        return redirect(url_for('distributor_bp.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    cur.execute("""
        SELECT * FROM orders 
        WHERE order_id = %s AND distributor_id = %s
    """, (order_id, distributor_id))
    order = cur.fetchone()
    
    if not order:
        flash("Order not found", "error")
        return redirect(url_for('distributor_order_bp.manage_orders'))
    
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