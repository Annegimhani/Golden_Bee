from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify

distributor_sell_bp = Blueprint('distributor_sell_bp', __name__,
                                 template_folder='templates')

bcrypt = None
mysql = None

# ── Helper ────────────────────────────────────────────────────────────────────

def get_distributor_id():
    return session.get('distributor_id')

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_distributor_id():
            flash('Please login first.', 'warning')
            return redirect(url_for('distributor_bp.login'))
        return f(*args, **kwargs)
    return decorated

# ── List / Manage Sales ───────────────────────────────────────────────────────

@distributor_sell_bp.route('/manage_sales')
@login_required
def manage_sales():
    distributor_id = get_distributor_id()
    cur = mysql.connection.cursor()

    search    = request.args.get('search', '').strip()
    status    = request.args.get('status', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to   = request.args.get('date_to', '').strip()

    query = """
        SELECT s.sale_id, s.product_name, s.quantity_sold, s.unit_price,
               s.total_amount, s.customer_name, s.customer_contact,
               s.sale_date, s.status, s.notes,
               s.variant_size, p.product_name AS cat_name
        FROM   sales s
        LEFT JOIN products p ON s.product_id = p.product_id
        WHERE  s.distributor_id = %s
    """
    params = [distributor_id]

    if search:
        query  += " AND (s.product_name LIKE %s OR s.customer_name LIKE %s)"
        params += [f'%{search}%', f'%{search}%']
    if status:
        query  += " AND s.status = %s"
        params.append(status)
    if date_from:
        query  += " AND DATE(s.sale_date) >= %s"
        params.append(date_from)
    if date_to:
        query  += " AND DATE(s.sale_date) <= %s"
        params.append(date_to)

    query += " ORDER BY s.sale_date DESC"

    cur.execute(query, params)
    sales = cur.fetchall()

    cur.execute("""
        SELECT COUNT(*),
               COALESCE(SUM(total_amount), 0),
               COALESCE(SUM(quantity_sold), 0)
        FROM   sales
        WHERE  distributor_id = %s
    """, [distributor_id])
    stats = cur.fetchone()

    cur.execute("""
        SELECT COUNT(*) FROM sales
        WHERE distributor_id = %s AND status = 'completed'
    """, [distributor_id])
    completed = cur.fetchone()[0]

    cur.close()

    username = session.get('distributor_name', 'Distributor')
    return render_template('manage_sales.html',
                           sales=sales, stats=stats,
                           completed=completed,
                           username=username,
                           search=search, status=status,
                           date_from=date_from, date_to=date_to)

# ── Record New Sale ───────────────────────────────────────────────────────────

@distributor_sell_bp.route('/sell_product', methods=['GET', 'POST'])
@login_required
def sell_product():
    distributor_id = get_distributor_id()
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        ds_stock_id      = request.form.get('stock_id')        # distributor_stock.stock_id
        quantity_sold    = int(request.form.get('quantity_sold', 0))
        unit_price       = float(request.form.get('unit_price', 0))
        customer_name    = request.form.get('customer_name', '').strip()
        customer_contact = request.form.get('customer_contact', '').strip()
        notes            = request.form.get('notes', '').strip()
        status           = request.form.get('status', 'completed')

        # Validate from distributor_stock — this table HAS distributor_id
        cur.execute("""
            SELECT ds.stock_id, p.product_name, ds.quantity,
                   ds.unit_price, ds.variant_size, ds.product_id
            FROM   distributor_stock ds
            JOIN   products p ON ds.product_id = p.product_id
            WHERE  ds.stock_id = %s AND ds.distributor_id = %s
        """, [ds_stock_id, distributor_id])
        stock = cur.fetchone()

        if not stock:
            flash('Invalid stock selected.', 'error')
        elif quantity_sold <= 0:
            flash('Quantity must be greater than 0.', 'error')
        elif quantity_sold > stock[2]:
            flash(f'Insufficient stock. Available: {stock[2]} units.', 'error')
        else:
            total_amount = quantity_sold * unit_price

            cur.execute("""
                INSERT INTO sales
                    (distributor_id, stock_id, product_id, product_name,
                     variant_size, quantity_sold, unit_price, total_amount,
                     customer_name, customer_contact, notes, status, sale_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, [distributor_id, ds_stock_id, stock[5], stock[1],
                  stock[4], quantity_sold, unit_price, total_amount,
                  customer_name, customer_contact, notes, status])

            # Deduct from distributor_stock (has distributor_id)
            cur.execute("""
                UPDATE distributor_stock
                SET    quantity = quantity - %s
                WHERE  stock_id = %s AND distributor_id = %s
            """, [quantity_sold, ds_stock_id, distributor_id])

            mysql.connection.commit()
            cur.close()
            flash(f'Sale recorded successfully! Total: LKR {total_amount:,.2f}', 'success')
            return redirect(url_for('distributor_sell_bp.manage_sales'))

    # Load only THIS distributor's stock with quantity > 0
    # index: 0=stock_id, 1=product_name, 2=quantity, 3=unit_price, 4=variant_size, 5=category_name
    cur.execute("""
        SELECT ds.stock_id, p.product_name, ds.quantity,
               ds.unit_price, ds.variant_size,
               c.category_name
        FROM   distributor_stock ds
        JOIN   products p ON ds.product_id = p.product_id
        LEFT JOIN category c ON p.category_id = c.category_id
        WHERE  ds.distributor_id = %s AND ds.quantity > 0
        ORDER  BY p.product_name
    """, [distributor_id])
    stock_items = cur.fetchall()
    cur.close()

    username = session.get('distributor_name', 'Distributor')
    return render_template('sell_product.html',
                           stock_items=stock_items,
                           username=username)

# ── AJAX: Get stock details ───────────────────────────────────────────────────

@distributor_sell_bp.route('/get_stock_details/<int:stock_id>')
@login_required
def get_stock_details(stock_id):
    distributor_id = get_distributor_id()
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT ds.stock_id, p.product_name, ds.quantity,
               ds.unit_price, ds.variant_size, p.shelf_life_days
        FROM   distributor_stock ds
        JOIN   products p ON ds.product_id = p.product_id
        WHERE  ds.stock_id = %s AND ds.distributor_id = %s
    """, [stock_id, distributor_id])
    row = cur.fetchone()
    cur.close()
    if row:
        return jsonify({
            'stock_id':        row[0],
            'product_name':    row[1],
            'quantity':        row[2],
            'unit_price':      float(row[3]),
            'variant_size':    row[4],
            'shelf_life_days': row[5]
        })
    return jsonify({'error': 'Not found'}), 404

# ── View Sale Detail ──────────────────────────────────────────────────────────

@distributor_sell_bp.route('/sale_detail/<int:sale_id>')
@login_required
def sale_detail(sale_id):
    distributor_id = get_distributor_id()
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT s.sale_id, s.product_name, s.quantity_sold, s.unit_price,
               s.total_amount, s.customer_name, s.customer_contact,
               s.sale_date, s.status, s.notes,
               s.variant_size, ds.quantity AS current_stock,
               p.shelf_life_days, s.stock_id
        FROM   sales s
        LEFT JOIN distributor_stock ds ON s.stock_id = ds.stock_id
        LEFT JOIN products p ON s.product_id = p.product_id
        WHERE  s.sale_id = %s AND s.distributor_id = %s
    """, [sale_id, distributor_id])
    sale = cur.fetchone()
    cur.close()

    if not sale:
        flash('Sale not found.', 'error')
        return redirect(url_for('distributor_sell_bp.manage_sales'))

    username = session.get('distributor_name', 'Distributor')
    return render_template('sale_detail.html', sale=sale, username=username)

# ── Update Sale ───────────────────────────────────────────────────────────────

@distributor_sell_bp.route('/update_sale/<int:sale_id>', methods=['GET', 'POST'])
@login_required
def update_sale(sale_id):
    distributor_id = get_distributor_id()
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT s.sale_id, s.product_name, s.quantity_sold, s.unit_price,
               s.total_amount, s.customer_name, s.customer_contact,
               s.sale_date, s.status, s.notes, s.stock_id,
               s.variant_size, ds.quantity AS current_stock
        FROM   sales s
        LEFT JOIN distributor_stock ds ON s.stock_id = ds.stock_id
        WHERE  s.sale_id = %s AND s.distributor_id = %s
    """, [sale_id, distributor_id])
    sale = cur.fetchone()

    if not sale:
        flash('Sale not found.', 'error')
        cur.close()
        return redirect(url_for('distributor_sell_bp.manage_sales'))

    if request.method == 'POST':
        new_quantity     = int(request.form.get('quantity_sold', sale[2]))
        new_price        = float(request.form.get('unit_price', sale[3]))
        customer_name    = request.form.get('customer_name', sale[5]).strip()
        customer_contact = request.form.get('customer_contact', sale[6]).strip()
        notes            = request.form.get('notes', sale[9]).strip()
        status           = request.form.get('status', sale[8])

        old_quantity = sale[2]
        qty_diff     = new_quantity - old_quantity

        if qty_diff > 0:
            cur.execute("""
                SELECT quantity FROM distributor_stock
                WHERE stock_id = %s AND distributor_id = %s
            """, [sale[10], distributor_id])
            avail = cur.fetchone()
            if not avail or avail[0] < qty_diff:
                flash(f'Insufficient stock. Available: {avail[0] if avail else 0} units.', 'error')
                cur.close()
                return render_template('update_sale.html', sale=sale,
                                       username=session.get('distributor_name', 'Distributor'))

        total_amount = new_quantity * new_price

        cur.execute("""
            UPDATE sales SET
                quantity_sold    = %s,
                unit_price       = %s,
                total_amount     = %s,
                customer_name    = %s,
                customer_contact = %s,
                notes            = %s,
                status           = %s
            WHERE sale_id = %s AND distributor_id = %s
        """, [new_quantity, new_price, total_amount,
              customer_name, customer_contact, notes,
              status, sale_id, distributor_id])

        # Adjust distributor_stock
        cur.execute("""
            UPDATE distributor_stock
            SET    quantity = quantity - %s
            WHERE  stock_id = %s AND distributor_id = %s
        """, [qty_diff, sale[10], distributor_id])

        mysql.connection.commit()
        cur.close()
        flash('Sale updated successfully!', 'success')
        return redirect(url_for('distributor_sell_bp.manage_sales'))

    cur.close()
    username = session.get('distributor_name', 'Distributor')
    return render_template('update_sale.html', sale=sale, username=username)

# ── Delete Sale ───────────────────────────────────────────────────────────────

@distributor_sell_bp.route('/delete_sale/<int:sale_id>', methods=['POST'])
@login_required
def delete_sale(sale_id):
    distributor_id = get_distributor_id()
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT quantity_sold, stock_id FROM sales
        WHERE sale_id = %s AND distributor_id = %s
    """, [sale_id, distributor_id])
    sale = cur.fetchone()

    if sale:
        # Restore stock to distributor_stock
        cur.execute("""
            UPDATE distributor_stock
            SET    quantity = quantity + %s
            WHERE  stock_id = %s AND distributor_id = %s
        """, [sale[0], sale[1], distributor_id])

        cur.execute("""
            DELETE FROM sales
            WHERE sale_id = %s AND distributor_id = %s
        """, [sale_id, distributor_id])

        mysql.connection.commit()
        flash('Sale deleted and stock restored.', 'success')
    else:
        flash('Sale not found.', 'error')

    cur.close()
    return redirect(url_for('distributor_sell_bp.manage_sales'))