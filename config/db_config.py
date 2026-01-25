from flask import Flask
from flask_mysqldb import MySQL


def init_db(app):
    app.config['MYSQL_HOST'] = 'localhost'
    app.config['MYSQL_USER'] = 'root'
    app.config['MYSQL_PASSWORD'] = '' 
    app.config['MYSQL_DB'] = 'golden_bee_db'
    app.config['MYSQL_PORT'] = 3307     
    return MySQL(app)


if __name__ == '__main__':
    app = Flask(__name__)
    mysql = init_db(app)

    with app.app_context():
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT DATABASE();")
            db_name = cursor.fetchone()
            print(f"Connected to database: {db_name[0]}")
        except Exception as e:
            print("Database connection failed:", e)

