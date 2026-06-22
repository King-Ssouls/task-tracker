from datetime import datetime
from flask_login import UserMixin
from .extensions import db, login_manager

# Модель пользователя 
class User(db.Model, UserMixin):
    
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    
    role = db.Column(db.String(30), nullable=False, default="developer")
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    projects = db.relationship("Project", backref="owner", lazy=True)
    tasks = db.relationship("Task", backref="assignee", lazy=True)
    comments = db.relationship("Comment", backref="author", lazy=True)
    attachments = db.relationship("Attachment", backref="uploader", lazy=True)
    
    
    def __repr__(self):
        return f"<User {self.full_name}>"
    
    
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))