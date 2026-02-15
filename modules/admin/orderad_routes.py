from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import MySQLdb
from datetime import datetime

# Injected from app.py
mysql = None

# Create Blueprint for order management
orderad_mgmt_bp = Blueprint(
    'orderad_mgmt_bp',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/admin_static'
)

# ==========================================
# SESSION CHECK HELPER FUNCTIONS
# ==========================================
def check_admin_session():
    """Check if admin is logged in"""
    return 'username' in session or 'admin_id' in session or 'admin_logged_in' in session

# ==========================================
# DATE FORMATTING HELPER
# ==========================================
def format_date_for_display(date_value):
    """Format date for display in template"""
    if not date_value:
        return "N/A"
    
    if isinstance(date_value, datetime):
        return date_value.strftime('%d/%m/%Y')
    
    if isinstance(date_value, str):
        try:
            if ' ' in date_value:
                dt = datetime.strptime(date_value.split('.')[0], '%Y-%m-%d %H:%M:%S')
                return dt.strftime('%d/%m/%Y')
            else:
                dt = datetime.strptime(date_value, '%Y-%m-%d')
                return dt.strftime('%d/%m/%Y')
        except:
            return date_value
    
    return str(date_value)

# ==========================================
# HELPER FUNCTION TO GET ORDERS DATA
# ==========================================
def get_orders_with_details(filter_status=None):
    """Fetch orders with real distributor and product details"""
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    orders = []
    
    try:
        base_query = """
            SELECT 
                oi.order_item_id as order_id,
                oi.order_item_id,
                oi.order_id as original_order_id,
                oi.product_id,
                oi.product_name,
                oi.category_name,
                oi.unit_price,
                oi.variant_size,
                oi.quantity as requested_quantity,
                oi.subtotal as total_price,
                o.order_date,
                o.distributor_id,
                o.status,
                o.total_amount,
                o.updated_quantity,
                o.updated_total_price,
                COALESCE(d.distributor_name, 'Unknown Distributor') as distributor_name,
                COALESCE(d.email, '') as distributor_email,
                COALESCE(d.contact_no, '') as distributor_phone,
                COALESCE(d.district, '') as district,
                COALESCE(d.province, '') as province,
                COALESCE(s.quantity, 0) as admin_stock,
                s.stock_id
            FROM order_items oi
            INNER JOIN orders o ON oi.order_id = o.order_id
            LEFT JOIN distributor d ON o.distributor_id = d.distributor_id
            LEFT JOIN stock s ON oi.product_id = s.product_id 
                AND oi.variant_size = s.variant_size
        """
        
        # Filter by status
        if filter_status and filter_status != 'all':
            base_query += " WHERE o.status = %s"
        
        base_query += " ORDER BY o.order_date DESC, oi.order_item_id DESC"
        
        if filter_status and filter_status != 'all':
            cur.execute(base_query, (filter_status,))
        else:
            cur.execute(base_query)
            
        orders = cur.fetchall()
        
        # Format dates and ensure variant_size is not None
        for order in orders:
            order['formatted_date'] = format_date_for_display(order.get('order_date'))
            if not order.get('variant_size'):
                order['variant_size'] = ''
            
    except Exception as e:
        print(f"Error fetching orders: {str(e)}")
    finally:
        cur.close()
    
    return orders

# ==========================================
# SEND MESSAGE TO DISTRIBUTOR
# ==========================================
def send_message_to_distributor(order_id, distributor_id, message_text, message_type='general'):
    """Send a message to distributor"""
    admin_id = session.get('admin_id', 1)
    cur = mysql.connection.cursor()
    
    try:
        # Check if messages table exists
        cur.execute("SHOW TABLES LIKE 'messages'")
        table_exists = cur.fetchone()
        
        if table_exists:
            cur.execute("""
                INSERT INTO messages (order_id, distributor_id, admin_id, message, message_type, created_at, is_read)
                VALUES (%s, %s, %s, %s, %s, NOW(), 0)
            """, (order_id, distributor_id, admin_id, message_text, message_type))
            mysql.connection.commit()
            return True
        else:
            print("Messages table does not exist")
            return False
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        mysql.connection.rollback()
        return False
    finally:
        cur.close()
    
    return False

# ==========================================
# ADMIN ORDER MANAGEMENT ROUTES
# ==========================================

@orderad_mgmt_bp.route('/manage_adorders')
def manage_adorders():
    """Main page to manage all orders"""
    if not check_admin_session():
        flash("Please log in as admin first", "error")
        return redirect('/admin/login')
    
    try:
        orders = get_orders_with_details()
        return render_template('manage_adorders.html', 
                              orders=orders,
                              filtered_status=None)
    except Exception as e:
        print(f"Error in manage_adorders: {str(e)}")
        flash("Error loading orders", "error")
        return render_template('manage_adorders.html', orders=[], filtered_status=None)

@orderad_mgmt_bp.route('/filter_orders/<status>')
def filter_orders(status):
    """Filter orders by status"""
    if not check_admin_session():
        flash("Please log in as admin first", "error")
        return redirect('/admin/login')
    
    valid_statuses = ['pending', 'accepted', 'rejected', 'all']
    
    if status not in valid_statuses:
        flash("Invalid status filter", "error")
        return redirect(url_for('orderad_mgmt_bp.manage_adorders'))
    
    try:
        orders = get_orders_with_details(status if status != 'all' else None)
        return render_template('manage_adorders.html', 
                              orders=orders,
                              filtered_status=status if status != 'all' else None)
    except Exception as e:
        print(f"Error in filter_orders: {str(e)}")
        flash("Error filtering orders", "error")
        return redirect(url_for('orderad_mgmt_bp.manage_adorders'))

@orderad_mgmt_bp.route('/update_order/<int:order_id>', methods=["POST"])
def update_order(order_id):
    """Update order status (accept, reject, pending) - WITH DISTRIBUTOR STOCK UPDATE"""
    if not check_admin_session():
        flash("Please log in as admin first", "error")
        return redirect('/admin/login')
    
    action = request.form.get('action')
    quantity = request.form.get('quantity')
    message = request.form.get('message', '').strip()
    
    if not action:
        flash("Invalid action", "error")
        return redirect(url_for('orderad_mgmt_bp.manage_adorders'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        # Get order details
        cur.execute("""
            SELECT 
                oi.*,
                o.distributor_id,
                o.status as current_status,
                o.order_id as original_order_id,
                s.quantity as current_stock,
                s.unit_price as stock_price,
                s.stock_id
            FROM order_items oi
            INNER JOIN orders o ON oi.order_id = o.order_id
            LEFT JOIN stock s ON oi.product_id = s.product_id 
                AND oi.variant_size = s.variant_size
            WHERE oi.order_item_id = %s
        """, (order_id,))
        
        order = cur.fetchone()
        
        if not order:
            flash("Order not found", "error")
            return redirect(url_for('orderad_mgmt_bp.manage_adorders'))
        
        distributor_id = order.get('distributor_id')
        original_order_id = order.get('original_order_id')
        current_stock = order.get('current_stock', 0)
        stock_id = order.get('stock_id')
        product_id = order.get('product_id')
        product_name = order.get('product_name', 'Product')
        variant_size = order.get('variant_size') or ''
        
        # Handle different actions
        if action == 'pending':
            # Set order back to pending
            cur.execute("""
                UPDATE orders 
                SET status = 'pending'
                WHERE order_id = %s
            """, (original_order_id,))
            mysql.connection.commit()
            flash("✏️ Order status updated to Pending", "success")
            
        elif action == 'accept':
            # Get and validate quantity
            if not quantity or int(quantity) <= 0:
                accept_quantity = order.get('quantity', 1)
            else:
                accept_quantity = int(quantity)
            
            # Check stock availability
            if not stock_id:
                flash("❌ Stock not found for this product!", "error")
                return redirect(url_for('orderad_mgmt_bp.manage_adorders'))
                
            if current_stock < accept_quantity:
                flash(f"❌ Insufficient stock! Available: {current_stock}, Requested: {accept_quantity}", "error")
                return redirect(url_for('orderad_mgmt_bp.manage_adorders'))
            
            # Calculate total price
            unit_price = order.get('stock_price') or order.get('unit_price', 0)
            new_total = float(unit_price) * accept_quantity
            
            # Update order_items
            cur.execute("""
                UPDATE order_items 
                SET quantity = %s, 
                    subtotal = %s
                WHERE order_item_id = %s
            """, (accept_quantity, new_total, order_id))
            
            # Update orders table
            cur.execute("""
                UPDATE orders 
                SET status = 'accepted',
                    updated_quantity = %s,
                    updated_total_price = %s,
                    total_amount = %s
                WHERE order_id = %s
            """, (accept_quantity, new_total, new_total, original_order_id))
            
            # Update admin stock - REDUCE quantity
            cur.execute("""
                UPDATE stock 
                SET quantity = quantity - %s
                WHERE stock_id = %s
            """, (accept_quantity, stock_id))
            
            # *** ADD TO DISTRIBUTOR'S STOCK ***
            # Check if distributor already has this product
            cur.execute("""
                SELECT stock_id, quantity 
                FROM distributor_stock 
                WHERE distributor_id = %s 
                  AND product_id = %s 
                  AND variant_size = %s
            """, (distributor_id, product_id, variant_size))
            
            dist_stock = cur.fetchone()
            
            if dist_stock:
                # Update existing distributor stock - ADD quantity
                new_dist_qty = dist_stock['quantity'] + accept_quantity
                cur.execute("""
                    UPDATE distributor_stock 
                    SET quantity = %s,
                        unit_price = %s,
                        last_updated = NOW()
                    WHERE stock_id = %s
                """, (new_dist_qty, unit_price, dist_stock['stock_id']))
            else:
                # Create new distributor stock entry
                cur.execute("""
                    INSERT INTO distributor_stock 
                    (distributor_id, product_id, variant_size, quantity, unit_price)
                    VALUES (%s, %s, %s, %s, %s)
                """, (distributor_id, product_id, variant_size, accept_quantity, unit_price))
            
            mysql.connection.commit()
            
            # Send message to distributor
            product_display = f"{product_name}"
            if variant_size:
                product_display += f" ({variant_size})"
                
            default_message = f"✅ ORDER ACCEPTED\n\nYour order has been approved!\n\nProduct: {product_display}\nApproved Quantity: {accept_quantity} units\nTotal Amount: Rs. {new_total:.2f}\n\n{accept_quantity} units have been added to your inventory.\n\nYour order will be processed and shipped soon."
            
            if message:
                default_message += f"\n\nAdmin Note: {message}"
            
            send_message_to_distributor(original_order_id, distributor_id, default_message, 'accept')
            
            flash(f"✅ Order accepted! {accept_quantity} units added to distributor's stock. Admin stock reduced by {accept_quantity} units.", "success")
            
        elif action == 'reject':
            # Reject order
            cur.execute("""
                UPDATE orders 
                SET status = 'rejected'
                WHERE order_id = %s
            """, (original_order_id,))
            
            mysql.connection.commit()
            
            # Send rejection message
            product_display = f"{product_name}"
            if variant_size:
                product_display += f" ({variant_size})"
                
            default_message = f"❌ ORDER REJECTED\n\nWe regret to inform you that your order has been rejected.\n\nProduct: {product_display}\nRequested Quantity: {order.get('quantity')} units"
            
            if message:
                default_message += f"\n\nReason: {message}"
            else:
                default_message += f"\n\nReason: Unable to fulfill at this time."
            
            default_message += "\n\nPlease contact us if you have any questions."
            
            send_message_to_distributor(original_order_id, distributor_id, default_message, 'reject')
            
            flash("❌ Order rejected. Message sent to distributor.", "success")
        
        else:
            flash("Invalid action specified", "error")
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error updating order: {str(e)}", "error")
        print(f"Error in update_order: {str(e)}")
    finally:
        cur.close()
    
    return redirect(url_for('orderad_mgmt_bp.manage_adorders'))

@orderad_mgmt_bp.route('/send_message/<int:order_id>', methods=["POST"])
def send_custom_message(order_id):
    """Send a custom message to distributor"""
    if not check_admin_session():
        flash("Please log in as admin first", "error")
        return redirect('/admin/login')
    
    message = request.form.get('message', '').strip()
    
    if not message:
        flash("Message cannot be empty", "error")
        return redirect(url_for('orderad_mgmt_bp.manage_adorders'))
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        cur.execute("""
            SELECT o.order_id as original_order_id, o.distributor_id, oi.product_name
            FROM order_items oi
            INNER JOIN orders o ON oi.order_id = o.order_id
            WHERE oi.order_item_id = %s
        """, (order_id,))
        result = cur.fetchone()
        
        if result:
            original_order_id = result['original_order_id']
            distributor_id = result['distributor_id']
            
            success = send_message_to_distributor(original_order_id, distributor_id, message, 'general')
            
            if success:
                flash("📧 Message sent successfully to distributor!", "success")
            else:
                flash("⚠️ Message could not be sent. Messages table may not exist.", "error")
        else:
            flash("Order not found", "error")
            
    except Exception as e:
        flash(f"Error sending message: {str(e)}", "error")
        print(f"Error in send_custom_message: {str(e)}")
    finally:
        cur.close()
    
    return redirect(url_for('orderad_mgmt_bp.manage_adorders'))

@orderad_mgmt_bp.route('/')
def order_dashboard():
    """Redirect to main orders page"""
    if not check_admin_session():
        flash("Please log in as admin first", "error")
        return redirect('/admin/login')
    return redirect(url_for('orderad_mgmt_bp.manage_adorders'))