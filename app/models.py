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


class Project(db.Model):

    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sprints = db.relationship(
        "Sprint",
        backref="project",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Project {self.name}>"


class Sprint(db.Model):

    __tablename__ = "sprints"

    id = db.Column(db.Integer, primary_key=True)

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)

    name = db.Column(db.String(150), nullable=False)

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    planned_points = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship(
        "Task",
        backref="sprint",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Sprint {self.name}>"


class Task(db.Model):

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)

    sprint_id = db.Column(db.Integer, db.ForeignKey("sprints.id"), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    #название статусов new, in_progress, review, done
    status = db.Column(db.String(30), nullable=False, default="new")

    story_points = db.Column(db.Integer, nullable=False, default=1)

    deadline = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    comments = db.relationship(
        "Comment",
        backref="task",
        lazy=True,
        cascade="all, delete-orphan",
    )

    attachments = db.relationship(
        "Attachment",
        backref="task",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Task {self.title}>"


class Comment(db.Model):

    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)

    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    text = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Comment {self.id}>"


class Attachment(db.Model):

    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)

    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Attachment {self.original_filename}>"