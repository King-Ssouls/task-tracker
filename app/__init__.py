import os
from flask import Flask
from .config import Config
from .extensions import db, migrate, login_manager


def create_app(test_config=None):
    app = Flask(__name__)

    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    
    # подключение flask логинов
    login_manager.init_app(app)
    login_manager.login_view = "main.login"

    from .routes import main
    app.register_blueprint(main)
    return app