from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import MySQLdb
from datetime import datetime

# Injected from app.py
mysql = None

# Create Blueprint for stock management
stock_mgmt_bp = Blueprint(
    'stock_mgmt', 
    __name__, 
    template_folder='templates',
    static_folder='static',
    static_url_path='/admin_static'
)

# Route to fix stock data (new route)
@stock_mgmt_bp.route('/fix_stock_data')
def fix_stock_data():
    try:
        cur = mysql.connection.cursor()
        
        # Fix missing product names
        cur.execute("""
            UPDATE stock s
            JOIN products p ON s.product_id = p.product_id
            SET s.product_name = p.product_name
            WHERE s.product_name IS NULL OR s.product_name = '' OR s.product_name = 'N/A'
        """)
        
        # Fix missing category names
        cur.execute("""
            UPDATE stock s
            JOIN products p ON s.product_id = p.product_id
            JOIN category c ON p.category_id = c.category_id
            SET 
                s.category_name = c.category_name,
                s.category_id = c.category_id
            WHERE s.category_name IS NULL OR s.category_name = '' OR s.category_name = 'N/A'
        """)
        
        mysql.connection.commit()
        
        fixed_count = cur.rowcount
        flash(f"Fixed {fixed_count} stock records!", "success")
        
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error fixing data: {str(e)}", "error")
    finally:
        cur.close()
    
    return redirect(url_for('stock_mgmt.manage_stock'))

# Route to manage stock (View all stock)
@stock_mgmt_bp.route('/manage_stock')
def manage_stock():
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # SIMPLE QUERY - Get all stock items
        cur.execute("""
            SELECT 
                s.stock_id,
                s.product_id,
                s.product_name,
                s.category_name,
                s.unit_price,
                s.variant_size,
                s.shelf_life_days,
                s.quantity,
                s.add_date,  # Get raw datetime
                s.category_id
            FROM stock s
            ORDER BY s.stock_id DESC
        """)
        
        stock_items = cur.fetchall()
        
        # Format dates in Python
        for item in stock_items:
            # Format unit price
            if item['unit_price']:
                try:
                    item['unit_price'] = float(item['unit_price'])
                except:
                    item['unit_price'] = 0.0
            
            # Format add_date
            if item['add_date']:
                try:
                    # If it's already a datetime object
                    if isinstance(item['add_date'], datetime):
                        item['formatted_date'] = item['add_date'].strftime('%Y-%m-%d %H:%M:%S')
                    # If it's a string
                    elif isinstance(item['add_date'], str):
                        # Try to parse it
                        try:
                            dt = datetime.strptime(item['add_date'], '%Y-%m-%d %H:%M:%S')
                            item['formatted_date'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            # If it's already in the right format
                            if '202' in item['add_date']:  # Check if it contains year
                                item['formatted_date'] = item['add_date']
                            else:
                                item['formatted_date'] = 'Invalid Date'
                    else:
                        item['formatted_date'] = str(item['add_date'])
                except Exception as e:
                    print(f"Error formatting date: {e}")
                    item['formatted_date'] = str(item['add_date'])
            else:
                item['formatted_date'] = 'N/A'
        
        # Debug: Check what data we have
        print(f"Total stock items: {len(stock_items)}")
        if stock_items:
            print("First item add_date:", stock_items[0].get('add_date'))
            print("First item formatted_date:", stock_items[0].get('formatted_date'))
        
    except Exception as e:
        print(f"Error in manage_stock: {str(e)}")
        stock_items = []
        flash(f"Error loading stock: {str(e)}", "error")
    finally:
        cur.close()
    
    return render_template('manage_stock.html', stock_items=stock_items)

# Route to add a new stock item
@stock_mgmt_bp.route('/add_stock', methods=["GET", "POST"])
def add_stock():
    if request.method == "POST":
        try:
            category_id = request.form.get("category_id")
            product_id = request.form.get("product_id")
            unit_price = request.form.get("unit_price")
            variant_size = request.form.get("variant_size")
            shelf_life_days = request.form.get("shelf_life_days")
            quantity = request.form.get("quantity")

            cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            # Validate required fields
            if not all([product_id, unit_price, quantity]):
                flash("Please fill in all required fields", "error")
                return redirect(url_for('stock_mgmt.add_stock'))
            
            # Get product and ALL related details
            cur.execute("""
                SELECT 
                    p.product_name,
                    p.unit_price as default_price,
                    p.variant_size as default_variant,
                    p.shelf_life_days as default_shelf_life,
                    c.category_id,
                    c.category_name
                FROM products p
                JOIN category c ON p.category_id = c.category_id
                WHERE p.product_id = %s
            """, (product_id,))
            
            result = cur.fetchone()
            
            if not result:
                flash("Product not found!", "error")
                return redirect(url_for('stock_mgmt.add_stock'))
            
            # Use form values or defaults
            product_name = result['product_name']
            final_category_id = result['category_id']
            final_category_name = result['category_name']
            final_unit_price = unit_price or result['default_price'] or 0
            final_variant_size = variant_size or result['default_variant'] or 'Standard'
            final_shelf_life = shelf_life_days or result['default_shelf_life'] or 0
            
            # Insert COMPLETE data into stock
            cur.execute("""
                INSERT INTO stock (
                    product_id, 
                    product_name, 
                    category_id, 
                    category_name, 
                    unit_price, 
                    variant_size, 
                    shelf_life_days, 
                    quantity
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                product_id, 
                product_name, 
                final_category_id, 
                final_category_name, 
                final_unit_price, 
                final_variant_size, 
                final_shelf_life, 
                quantity
            ))
            
            mysql.connection.commit()
            flash("Stock added successfully!", "success")
            return redirect(url_for('stock_mgmt.manage_stock'))
            
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error adding stock: {str(e)}", "error")
            print(f"Error details: {str(e)}")
        finally:
            if cur:
                cur.close()

    # GET request - fetch categories
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT category_id, category_name FROM category ORDER BY category_name")
        categories = cur.fetchall()
        
        if not categories:
            flash("No categories found. Please add categories first.", "warning")
            
    except Exception as e:
        print(f"Error loading categories: {str(e)}")
        categories = []
        flash(f"Error loading categories: {str(e)}", "error")
    finally:
        cur.close()

    return render_template('add_stock.html', categories=categories)

# Route to update stock item - FIXED VERSION
@stock_mgmt_bp.route('/update_stock/<int:stock_id>', methods=["GET", "POST"])
def update_stock(stock_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        if request.method == "POST":
            # Get form data
            product_id = request.form.get("product_id")
            unit_price = request.form.get("unit_price")
            variant_size = request.form.get("variant_size")
            shelf_life_days = request.form.get("shelf_life_days")
            quantity = request.form.get("quantity")
            
            # Get product and category details for the selected product
            cur.execute("""
                SELECT p.product_name, c.category_id, c.category_name
                FROM products p
                JOIN category c ON p.category_id = c.category_id
                WHERE p.product_id = %s
            """, (product_id,))
            
            product_info = cur.fetchone()
            
            if not product_info:
                flash("Product not found!", "error")
                return redirect(url_for('stock_mgmt.manage_stock'))
            
            product_name = product_info['product_name']
            category_id = product_info['category_id']
            category_name = product_info['category_name']
            
            # Update the stock item with ALL fields
            cur.execute("""
                UPDATE stock SET 
                    product_id = %s,
                    product_name = %s,
                    category_id = %s,
                    category_name = %s,
                    unit_price = %s,
                    variant_size = %s,
                    shelf_life_days = %s,
                    quantity = %s
                WHERE stock_id = %s
            """, (
                product_id, 
                product_name, 
                category_id, 
                category_name, 
                unit_price, 
                variant_size, 
                shelf_life_days, 
                quantity, 
                stock_id
            ))
            
            mysql.connection.commit()
            flash("Stock updated successfully!", "success")
            return redirect(url_for('stock_mgmt.manage_stock'))
        
        # GET request - fetch the stock item and dropdown data
        cur.execute("SELECT * FROM stock WHERE stock_id = %s", (stock_id,))
        stock_item = cur.fetchone()
        
        if not stock_item:
            flash("Stock item not found.", "error")
            return redirect(url_for('stock_mgmt.manage_stock'))
        
        # Fetch categories for dropdown
        cur.execute("SELECT category_id, category_name FROM category ORDER BY category_name")
        categories = cur.fetchall()
        
        # Fetch products for dropdown (all products initially)
        cur.execute("SELECT product_id, product_name FROM products ORDER BY product_name")
        products = cur.fetchall()
        
        return render_template('update_stock.html', 
                             stock_item=stock_item, 
                             categories=categories, 
                             products=products)
        
    except Exception as e:
        mysql.connection.rollback() if request.method == "POST" else None
        flash(f"Error updating stock: {str(e)}", "error")
        print(f"Update error: {str(e)}")
        return redirect(url_for('stock_mgmt.manage_stock'))
    finally:
        cur.close()

# Route to delete stock item
@stock_mgmt_bp.route('/delete_stock/<int:stock_id>', methods=["POST"])
def delete_stock(stock_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM stock WHERE stock_id = %s", (stock_id,))
        mysql.connection.commit()
        flash("Stock deleted successfully", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error deleting stock: {str(e)}", "error")
    finally:
        cur.close()

    return redirect(url_for('stock_mgmt.manage_stock'))

# Route to get products based on the selected category (AJAX endpoint)
@stock_mgmt_bp.route('/get_products/<category_id>', methods=['GET'])
def get_products(category_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Check if category_id is valid
        if not category_id or category_id == 'undefined' or category_id == 'null':
            return jsonify({'products': []})
        
        # Get products for the category
        cur.execute("""
            SELECT product_id, product_name 
            FROM products 
            WHERE category_id = %s
            ORDER BY product_name
        """, (category_id,))
        
        products = cur.fetchall()
        
        # Format the response
        product_list = []
        for product in products:
            product_list.append({
                'product_id': product['product_id'],
                'product_name': product['product_name']
            })
            
        return jsonify({'products': product_list})
        
    except Exception as e:
        print(f"Error in get_products: {str(e)}")
        return jsonify({'products': [], 'error': str(e)})
    finally:
        cur.close()

# Route to get product details (AJAX endpoint) - FIXED VERSION
@stock_mgmt_bp.route('/get_product_details/<product_id>', methods=['GET'])
def get_product_details(product_id):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cur.execute("""
            SELECT 
                p.product_name,
                p.unit_price,
                p.variant_size,
                p.shelf_life_days,
                c.category_id,
                c.category_name
            FROM products p
            LEFT JOIN category c ON p.category_id = c.category_id
            WHERE p.product_id = %s
        """, (product_id,))
        
        product = cur.fetchone()
        
        if product:
            return jsonify({
                'success': True,
                'product_name': product['product_name'],
                'unit_price': str(product['unit_price']) if product['unit_price'] is not None else '0',
                'variant_size': product['variant_size'] or '',
                'shelf_life_days': product['shelf_life_days'] or '0',
                'category_id': product['category_id'] or '',
                'category_name': product['category_name'] or ''
            })
        else:
            return jsonify({'success': False, 'message': 'Product not found'})
            
    except Exception as e:
        print(f"Error in get_product_details: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()

# Route to search stock items
@stock_mgmt_bp.route('/search_stock', methods=['GET'])
def search_stock():
    search_query = request.args.get('q', '')
    
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        if search_query:
            cur.execute("""
                SELECT 
                    s.*,
                    COALESCE(s.product_name, p.product_name, 'N/A') as display_product_name,
                    COALESCE(s.category_name, c.category_name, 'N/A') as display_category_name
                FROM stock s
                LEFT JOIN products p ON s.product_id = p.product_id
                LEFT JOIN category c ON s.category_id = c.category_id OR p.category_id = c.category_id
                WHERE s.product_name LIKE %s 
                   OR s.category_name LIKE %s
                   OR p.product_name LIKE %s
                   OR c.category_name LIKE %s
                   OR s.variant_size LIKE %s
                ORDER BY s.stock_id DESC
            """, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', 
                  f'%{search_query}%', f'%{search_query}%'))
        else:
            cur.execute("""
                SELECT 
                    s.*,
                    COALESCE(s.product_name, p.product_name, 'N/A') as display_product_name,
                    COALESCE(s.category_name, c.category_name, 'N/A') as display_category_name
                FROM stock s
                LEFT JOIN products p ON s.product_id = p.product_id
                LEFT JOIN category c ON s.category_id = c.category_id OR p.category_id = c.category_id
                ORDER BY s.stock_id DESC
            """)
        
        stock_items = cur.fetchall()
        
        return render_template('manage_stock.html', 
                             stock_items=stock_items, 
                             search_query=search_query)
        
    except Exception as e:
        flash(f"Error searching stock: {str(e)}", "error")
        return redirect(url_for('stock_mgmt.manage_stock'))
    finally:
        cur.close()

# Route to get products by category name (for update form)
@stock_mgmt_bp.route('/get_products_by_category/<category_name>', methods=['GET'])
def get_products_by_category(category_name):
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # First get category_id from category_name
        cur.execute("SELECT category_id FROM category WHERE category_name = %s", (category_name,))
        category = cur.fetchone()
        
        if not category:
            return jsonify({'products': []})
        
        # Get products for this category
        cur.execute("""
            SELECT product_id, product_name 
            FROM products 
            WHERE category_id = %s
            ORDER BY product_name
        """, (category['category_id'],))
        
        products = cur.fetchall()
        return jsonify({'products': products})
        
    except Exception as e:
        print(f"Error getting products by category: {str(e)}")
        return jsonify({'products': []})
    finally:
        cur.close()


# Add this route to your stock_mgmt_bp blueprint
@stock_mgmt_bp.route('/stock_summary')
def stock_summary():
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Query to get total quantity and total price per product
        cur.execute("""
            SELECT 
                s.product_id,
                COALESCE(s.product_name, p.product_name, 'Unknown Product') as product_name,
                COALESCE(s.category_name, c.category_name, 'Uncategorized') as category_name,
                COALESCE(s.unit_price, p.unit_price, 0) as unit_price,
                COALESCE(s.variant_size, p.variant_size, 'Standard') as variant_size,
                SUM(s.quantity) as total_quantity,
                SUM(s.quantity * COALESCE(s.unit_price, p.unit_price, 0)) as total_price
            FROM stock s
            LEFT JOIN products p ON s.product_id = p.product_id
            LEFT JOIN category c ON s.category_id = c.category_id OR p.category_id = c.category_id
            WHERE s.quantity > 0
            GROUP BY 
                s.product_id, 
                s.product_name, 
                s.category_name,
                s.unit_price,
                s.variant_size,
                p.product_name,
                p.unit_price,
                p.variant_size,
                c.category_name
            ORDER BY total_price DESC, product_name
        """)
        
        stock_summary = cur.fetchall()
        
        # Calculate grand totals
        total_items = len(stock_summary)
        total_quantity_all = sum(item['total_quantity'] or 0 for item in stock_summary)
        total_value_all = sum(item['total_price'] or 0 for item in stock_summary)
        
        # Format currency values
        for item in stock_summary:
            item['unit_price'] = float(item['unit_price'] or 0)
            item['total_price'] = float(item['total_price'] or 0)
        
    except Exception as e:
        print(f"Error in stock_summary: {str(e)}")
        stock_summary = []
        total_items = 0
        total_quantity_all = 0
        total_value_all = 0
        flash(f"Error loading stock summary: {str(e)}", "error")
    finally:
        cur.close()
    
    return render_template('stock_summary.html', 
                         stock_summary=stock_summary,
                         total_items=total_items,
                         total_quantity_all=total_quantity_all,
                         total_value_all=total_value_all)        