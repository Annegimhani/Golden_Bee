"""
Distributor Stock Management Routes
Handles distributor's personal inventory management
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
import MySQLdb
from datetime import datetime

# Injected from app.py
mysql = None
bcrypt = None

# Create Blueprint
distributor_stock_bp = Blueprint(
    'distributor_stock_bp',
    __name__,
    template_folder='templates',
    static_folder='static'
)

# ==========================================
# SESSION CHECK
# ==========================================
def check_distributor_session():
    """Check if distributor is logged in"""
    return 'distributor_id' in session

# ==========================================
# GET DISTRIBUTOR STOCK
# ==========================================
def get_distributor_stock(distributor_id):
    """Get all stock items for a distributor with product details"""
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        # Join with stock table to get product and category info
        query = """
            SELECT 
                ds.stock_id,
                ds.distributor_id,
                ds.product_id,
                ds.variant_size,
                ds.quantity,
                ds.unit_price,
                ds.last_updated,
                COALESCE(s.product_name, 'Unknown Product') as product_name,
                COALESCE(s.category_name, 'Uncategorized') as category_name,
                (ds.quantity * ds.unit_price) as total_value
            FROM distributor_stock ds
            LEFT JOIN stock s ON ds.product_id = s.product_id 
                AND ds.variant_size = s.variant_size
            WHERE ds.distributor_id = %s
            ORDER BY ds.last_updated DESC
        """
        
        print(f"DEBUG: Fetching stock for distributor_id: {distributor_id}")
        cur.execute(query, (distributor_id,))
        
        stock_items = cur.fetchall()
        print(f"DEBUG: Found {len(stock_items)} stock items")
        
        # Format dates
        for item in stock_items:
            print(f"DEBUG: Item - ID: {item.get('stock_id')}, Product: {item.get('product_name')}, Qty: {item.get('quantity')}")
            
            if item.get('last_updated'):
                if isinstance(item['last_updated'], datetime):
                    item['formatted_date'] = item['last_updated'].strftime('%d/%m/%Y %H:%M')
                else:
                    try:
                        dt = datetime.strptime(str(item['last_updated']), '%Y-%m-%d %H:%M:%S')
                        item['formatted_date'] = dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        item['formatted_date'] = str(item['last_updated'])
            else:
                item['formatted_date'] = 'N/A'
            
            # Ensure variant_size is not None
            if not item.get('variant_size'):
                item['variant_size'] = ''
            
            # Ensure total_value is calculated
            if item.get('total_value') is None:
                item['total_value'] = float(item.get('quantity', 0)) * float(item.get('unit_price', 0))
                
        print(f"DEBUG: Returning {len(stock_items)} items to template")
        return stock_items
        
    except Exception as e:
        print(f"ERROR fetching distributor stock: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        cur.close()

# ==========================================
# ADD STOCK TO DISTRIBUTOR INVENTORY
# ==========================================
def add_distributor_stock(distributor_id, product_id, variant_size, quantity, unit_price):
    """
    Add or update stock for a distributor
    If product+variant exists, add to existing quantity
    Otherwise create new stock entry
    """
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        # Check if this product+variant already exists for distributor
        cur.execute("""
            SELECT stock_id, quantity 
            FROM distributor_stock 
            WHERE distributor_id = %s 
              AND product_id = %s 
              AND variant_size = %s
        """, (distributor_id, product_id, variant_size or ''))
        
        existing = cur.fetchone()
        
        if existing:
            # Update existing stock - ADD to current quantity
            new_quantity = existing['quantity'] + quantity
            cur.execute("""
                UPDATE distributor_stock 
                SET quantity = %s,
                    unit_price = %s,
                    last_updated = NOW()
                WHERE stock_id = %s
            """, (new_quantity, unit_price, existing['stock_id']))
            
            mysql.connection.commit()
            return True, f"Added {quantity} units. New total: {new_quantity}"
        else:
            # Insert new stock entry
            cur.execute("""
                INSERT INTO distributor_stock 
                (distributor_id, product_id, variant_size, quantity, unit_price)
                VALUES (%s, %s, %s, %s, %s)
            """, (distributor_id, product_id, variant_size or '', quantity, unit_price))
            
            mysql.connection.commit()
            return True, f"New product added with {quantity} units"
            
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error adding distributor stock: {str(e)}")
        return False, f"Error: {str(e)}"
    finally:
        cur.close()

# ==========================================
# GET STOCK STATISTICS
# ==========================================
def get_stock_stats(distributor_id):
    """Get stock statistics for dashboard"""
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        # Total products
        cur.execute("""
            SELECT COUNT(DISTINCT product_id) as total_products
            FROM distributor_stock
            WHERE distributor_id = %s
        """, (distributor_id,))
        stats = cur.fetchone()
        total_products = stats['total_products'] if stats else 0
        
        # Total quantity
        cur.execute("""
            SELECT SUM(quantity) as total_quantity
            FROM distributor_stock
            WHERE distributor_id = %s
        """, (distributor_id,))
        stats = cur.fetchone()
        total_quantity = stats['total_quantity'] if stats and stats['total_quantity'] else 0
        
        # Total value
        cur.execute("""
            SELECT SUM(quantity * unit_price) as total_value
            FROM distributor_stock
            WHERE distributor_id = %s
        """, (distributor_id,))
        stats = cur.fetchone()
        total_value = stats['total_value'] if stats and stats['total_value'] else 0
        
        # Low stock items (quantity < 10)
        cur.execute("""
            SELECT COUNT(*) as low_stock_count
            FROM distributor_stock
            WHERE distributor_id = %s AND quantity < 10
        """, (distributor_id,))
        stats = cur.fetchone()
        low_stock = stats['low_stock_count'] if stats else 0
        
        result = {
            'total_products': total_products,
            'total_quantity': total_quantity,
            'total_value': float(total_value),
            'low_stock_count': low_stock
        }
        
        print(f"DEBUG: Stats calculated: {result}")
        return result
        
    except Exception as e:
        print(f"Error getting stock stats: {str(e)}")
        return {
            'total_products': 0,
            'total_quantity': 0,
            'total_value': 0.0,
            'low_stock_count': 0
        }
    finally:
        cur.close()

# ==========================================
# ROUTES
# ==========================================

@distributor_stock_bp.route('/my_stock')
def my_stock():
    """View distributor's personal stock"""
    if not check_distributor_session():
        flash("Please log in first", "error")
        return redirect('/distributor/login')
    
    distributor_id = session.get('distributor_id')
    distributor_name = session.get('distributor_name', 'Distributor')
    
    print(f"DEBUG: ========================================")
    print(f"DEBUG: Loading My Stock page")
    print(f"DEBUG: Logged in distributor_id: {distributor_id}")
    print(f"DEBUG: Distributor name: {distributor_name}")
    
    # Get stock items
    stock_items = get_distributor_stock(distributor_id)
    print(f"DEBUG: Retrieved {len(stock_items)} stock items for template")
    
    # Get statistics
    stats = get_stock_stats(distributor_id)
    print(f"DEBUG: Stats: {stats}")
    print(f"DEBUG: ========================================")
    
    return render_template('distributor_my_stock.html',
                          stock_items=stock_items,
                          stats=stats,
                          username=distributor_name)

@distributor_stock_bp.route('/stock_details/<int:stock_id>')
def stock_details(stock_id):
    """View details of a specific stock item"""
    if not check_distributor_session():
        flash("Please log in first", "error")
        return redirect('/distributor/login')
    
    distributor_id = session.get('distributor_id')
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        cur.execute("""
            SELECT 
                ds.*,
                p.product_name,
                p.product_image,
                p.description
            FROM distributor_stock ds
            LEFT JOIN products p ON ds.product_id = p.product_id
            WHERE ds.stock_id = %s AND ds.distributor_id = %s
        """, (stock_id, distributor_id))
        
        stock_item = cur.fetchone()
        
        if not stock_item:
            flash("Stock item not found", "error")
            return redirect(url_for('distributor_stock_bp.my_stock'))
        
        return render_template('distributor_stock_details.html', stock=stock_item)
        
    except Exception as e:
        flash(f"Error loading stock details: {str(e)}", "error")
        return redirect(url_for('distributor_stock_bp.my_stock'))
    finally:
        cur.close()

@distributor_stock_bp.route('/update_stock/<int:stock_id>', methods=['POST'])
def update_stock(stock_id):
    """Update stock quantity manually"""
    if not check_distributor_session():
        flash("Please log in first", "error")
        return redirect('/distributor/login')
    
    distributor_id = session.get('distributor_id')
    new_quantity = request.form.get('quantity')
    
    if not new_quantity or int(new_quantity) < 0:
        flash("Invalid quantity", "error")
        return redirect(url_for('distributor_stock_bp.my_stock'))
    
    cur = mysql.connection.cursor()
    
    try:
        cur.execute("""
            UPDATE distributor_stock 
            SET quantity = %s,
                last_updated = NOW()
            WHERE stock_id = %s AND distributor_id = %s
        """, (new_quantity, stock_id, distributor_id))
        
        mysql.connection.commit()
        flash(f"✅ Stock updated to {new_quantity} units", "success")
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error updating stock: {str(e)}", "error")
    finally:
        cur.close()
    
    return redirect(url_for('distributor_stock_bp.my_stock'))

@distributor_stock_bp.route('/api/stock_status/<int:product_id>')
def api_stock_status(product_id):
    """API endpoint to check stock status for a product"""
    if not check_distributor_session():
        return jsonify({'error': 'Not authenticated'}), 401
    
    distributor_id = session.get('distributor_id')
    variant_size = request.args.get('variant_size', '')
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        cur.execute("""
            SELECT quantity, unit_price
            FROM distributor_stock
            WHERE distributor_id = %s 
              AND product_id = %s 
              AND variant_size = %s
        """, (distributor_id, product_id, variant_size))
        
        stock = cur.fetchone()
        
        if stock:
            return jsonify({
                'has_stock': True,
                'quantity': stock['quantity'],
                'unit_price': float(stock['unit_price'])
            })
        else:
            return jsonify({
                'has_stock': False,
                'quantity': 0,
                'unit_price': 0
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close()