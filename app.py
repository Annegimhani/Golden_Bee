from flask import Flask
from flask_bcrypt import Bcrypt
from config.db_config import init_db

# Import routes from admin and distributor modules
from modules.admin import routes as admin_routes
from modules.distributor import routes as distributor_routes

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# Initialize MySQL and Bcrypt
bcrypt = Bcrypt(app)
mysql = init_db(app)

# Inject bcrypt and mysql into the routes
admin_routes.bcrypt = bcrypt
admin_routes.mysql = mysql
distributor_routes.bcrypt = bcrypt
distributor_routes.mysql = mysql

# Register Blueprints
app.register_blueprint(admin_routes.admin_bp, url_prefix='/admin')
app.register_blueprint(distributor_routes.distributor_bp, url_prefix='/distributor')

if __name__ == '__main__':
    app.run(debug=True)
