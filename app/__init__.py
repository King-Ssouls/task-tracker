import os
from flask import Flask
from .config import Confing
from .extensions import db, migrate, login_manager

def create_app():
    app = Flask(__name__)
    
    app.config.from_object(Confing)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    
    
    db.init_app(app)
    migrate.init_app(app, db)
    
    # подключение flask логинов
    login_manager.init_app(app)
    login_manager.login_view = "main.login"
    
    from .routes import main
    return app