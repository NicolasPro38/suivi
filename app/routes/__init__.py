from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    from app.routes.api import api
    app.register_blueprint(api)

    from flask import render_template
    @app.route('/')
    @app.route('/dispatch/')
    @app.route('/dispatch')
    def index():
        return render_template('index.html')

    return app