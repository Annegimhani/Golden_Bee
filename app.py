from flask import Flask
from flask_bcrypt import Bcrypt
from config.db_config import init_db

# Import routes from admin, distributor, category, and product modules
from modules.admin import routes as admin_routes
from modules.admin import distributor_routes as distributor_mgmt_routes
from modules.admin import category_routes as category_mgmt_routes
from modules.admin import product_routes as product_mgmt_routes
from modules.admin import stock_routes as stock_mgmt_routes
from modules.admin import orderad_routes as orderad_mgmt_routes

from modules.distributor import routes as distributor_routes
from modules.distributor import order_routes as distributor_order_routes
from modules.distributor import stock_routes as distributor_stock_routes
from modules.distributor import profile_routes as distributor_profile_routes
from modules.distributor import return_stock_routes as distributor_return_stock_routes
from modules.distributor import sell_routes as distributor_sell_routes

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Use an environment variable for production

# Initialize MySQL and Bcrypt
bcrypt = Bcrypt(app)
mysql = init_db(app)

if mysql is None:
    raise RuntimeError("MySQL connection is not initialized.")

# ── Inject bcrypt and mysql into routes ──────────────────────────────────────

admin_routes.bcrypt = bcrypt
admin_routes.mysql = mysql

distributor_routes.bcrypt = bcrypt
distributor_routes.mysql = mysql

distributor_mgmt_routes.bcrypt = bcrypt
distributor_mgmt_routes.mysql = mysql

category_mgmt_routes.bcrypt = bcrypt
category_mgmt_routes.mysql = mysql

product_mgmt_routes.bcrypt = bcrypt
product_mgmt_routes.mysql = mysql

stock_mgmt_routes.bcrypt = bcrypt
stock_mgmt_routes.mysql = mysql

orderad_mgmt_routes.bcrypt = bcrypt
orderad_mgmt_routes.mysql = mysql

distributor_order_routes.bcrypt = bcrypt
distributor_order_routes.mysql = mysql

distributor_stock_routes.bcrypt = bcrypt
distributor_stock_routes.mysql = mysql

distributor_profile_routes.bcrypt = bcrypt
distributor_profile_routes.mysql = mysql

distributor_return_stock_routes.bcrypt = bcrypt   # ✅ Return Stock
distributor_return_stock_routes.mysql = mysql     # ✅ Return Stock

distributor_sell_routes.bcrypt = bcrypt
distributor_sell_routes.mysql  = mysql

# ── Register Blueprints ───────────────────────────────────────────────────────

app.register_blueprint(admin_routes.admin_bp,                url_prefix='/admin')
app.register_blueprint(distributor_mgmt_routes.distributor_mgmt_bp, url_prefix='/admin')
app.register_blueprint(category_mgmt_routes.category_mgmt_bp,      url_prefix='/admin')
app.register_blueprint(product_mgmt_routes.product_mgmt_bp,         url_prefix='/admin')
app.register_blueprint(stock_mgmt_routes.stock_mgmt_bp,             url_prefix='/admin')
app.register_blueprint(orderad_mgmt_routes.orderad_mgmt_bp,         url_prefix='/admin')

app.register_blueprint(distributor_routes.distributor_bp,             url_prefix='/distributor')
app.register_blueprint(distributor_order_routes.distributor_order_bp, url_prefix='/distributor')
app.register_blueprint(distributor_stock_routes.distributor_stock_bp, url_prefix='/distributor')
app.register_blueprint(distributor_profile_routes.distributor_profile_bp, url_prefix='/distributor')
app.register_blueprint(distributor_return_stock_routes.distributor_return_stock_bp, url_prefix='/distributor')  # ✅ Return Stock
app.register_blueprint(distributor_sell_routes.distributor_sell_bp, url_prefix='/distributor')


if __name__ == '__main__':
    app.run(debug=True)