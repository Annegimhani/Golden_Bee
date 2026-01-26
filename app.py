from flask import Flask
from flask_bcrypt import Bcrypt
from config.db_config import init_db

# Import routes from admin, distributor, category, and product modules
from modules.admin import routes as admin_routes
from modules.admin import distributor_routes as distributor_mgmt_routes
from modules.admin import category_routes as category_mgmt_routes  # Import category routes
from modules.admin import product_routes as product_mgmt_routes  # Import product management routes
from modules.admin import stock_routes as stock_mgmt_routes

from modules.distributor import routes as distributor_routes

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Use an environment variable for production

# Initialize MySQL and Bcrypt
bcrypt = Bcrypt(app)
mysql = init_db(app)  # Initialize MySQL connection here

# Ensure MySQL is initialized
if mysql is None:
    raise RuntimeError("MySQL connection is not initialized.")

# Inject bcrypt and mysql into the routes
admin_routes.bcrypt = bcrypt
admin_routes.mysql = mysql
distributor_routes.bcrypt = bcrypt
distributor_routes.mysql = mysql
distributor_mgmt_routes.bcrypt = bcrypt  # Inject bcrypt into the distributor management blueprint
distributor_mgmt_routes.mysql = mysql  # Inject mysql into the distributor management blueprint
category_mgmt_routes.bcrypt = bcrypt  # Inject bcrypt into the category management blueprint
category_mgmt_routes.mysql = mysql  # Inject mysql into the category management blueprint
product_mgmt_routes.bcrypt = bcrypt  # Inject bcrypt into the product management blueprint
product_mgmt_routes.mysql = mysql  # Inject mysql into the product management blueprint
stock_mgmt_routes.bcrypt = bcrypt  # Inject bcrypt into the stock management blueprint
stock_mgmt_routes.mysql = mysql 


# Register Blueprints
app.register_blueprint(admin_routes.admin_bp, url_prefix='/admin')
app.register_blueprint(distributor_mgmt_routes.distributor_mgmt_bp, url_prefix='/admin') 
app.register_blueprint(category_mgmt_routes.category_mgmt_bp, url_prefix='/admin')  # Register category management blueprint
app.register_blueprint(product_mgmt_routes.product_mgmt_bp, url_prefix='/admin')  # Register product management blueprint
app.register_blueprint(stock_mgmt_routes.stock_mgmt_bp, url_prefix='/admin')

app.register_blueprint(distributor_routes.distributor_bp, url_prefix='/distributor')

if __name__ == '__main__':
    app.run(debug=True)
