from flask import Blueprint, render_template, request, redirect, url_for, session, flash
import MySQLdb.cursors

mysql = None
bcrypt = None

distributor_return_stock_bp = Blueprint('distributor_return_stock', __name__)


def get_distributor_id():
    return session.get('distributor_id')


# ── History page (main return stock page) ────────────────────────────────────

@distributor_return_stock_bp.route('/return-stock', methods=['GET'])
def return_stock():
    distributor_id = get_distributor_id()
    if not distributor_id:
        return redirect(url_for('distributor_bp.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT
            sr.return_id,
            p.product_name,
            sr.variant_size,
            sr.quantity_returned,
            sr.reason,
            sr.status,
            sr.created_at
        FROM stock_returns sr
        JOIN products p ON sr.product_id = p.product_id
        WHERE sr.distributor_id = %s
        ORDER BY sr.created_at DESC
    """, (distributor_id,))
    return_history = cur.fetchall()

    cur.close()
    return render_template('return_stock.html', return_history=return_history)


# ── New return form page ──────────────────────────────────────────────────────

@distributor_return_stock_bp.route('/return-stock/new', methods=['GET'])
def return_stock_form():
    distributor_id = get_distributor_id()
    if not distributor_id:
        return redirect(url_for('distributor_bp.login'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT
            ds.stock_id,
            ds.product_id,
            ds.variant_size,
            ds.quantity,
            ds.unit_price,
            p.product_name
        FROM distributor_stock ds
        JOIN products p ON ds.product_id = p.product_id
        WHERE ds.distributor_id = %s AND ds.quantity > 0
        ORDER BY p.product_name
    """, (distributor_id,))
    stock_list = cur.fetchall()

    cur.close()
    return render_template('return_stock_form.html', stock_list=stock_list)


# ── Submit handler ────────────────────────────────────────────────────────────

@distributor_return_stock_bp.route('/return-stock/submit', methods=['POST'])
def submit_return():
    distributor_id = get_distributor_id()
    if not distributor_id:
        return redirect(url_for('distributor_bp.login'))

    stock_id          = request.form.get('stock_id')
    quantity_returned = request.form.get('quantity_returned', type=int)
    reason            = request.form.get('reason', '').strip()

    if not stock_id or not quantity_returned or quantity_returned <= 0:
        flash('Please select a stock item and enter a valid quantity.', 'warning')
        return redirect(url_for('distributor_return_stock.return_stock_form'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    cur.execute("""
        SELECT stock_id, product_id, variant_size, quantity
        FROM distributor_stock
        WHERE stock_id = %s AND distributor_id = %s
    """, (stock_id, distributor_id))
    stock = cur.fetchone()

    if not stock:
        flash('Stock item not found.', 'error')
        cur.close()
        return redirect(url_for('distributor_return_stock.return_stock_form'))

    if quantity_returned > stock['quantity']:
        flash(f"Cannot return more than available quantity ({stock['quantity']}).", 'warning')
        cur.close()
        return redirect(url_for('distributor_return_stock.return_stock_form'))

    cur.execute("""
        INSERT INTO stock_returns
            (stock_id, distributor_id, product_id, variant_size, quantity_returned, reason, status)
        VALUES (%s, %s, %s, %s, %s, %s, 'pending')
    """, (
        stock_id,
        distributor_id,
        stock['product_id'],
        stock['variant_size'],
        quantity_returned,
        reason
    ))

    cur.execute("""
        UPDATE distributor_stock
        SET quantity = quantity - %s, last_updated = NOW()
        WHERE stock_id = %s
    """, (quantity_returned, stock_id))

    mysql.connection.commit()
    cur.close()

    flash('Return request submitted successfully! Awaiting admin approval.', 'success')
    return redirect(url_for('distributor_return_stock.return_stock'))