from datetime import datetime
from flask_login import UserMixin
from .extensions import db, login_manager

#модель пользователя 
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

    #связь пользователей с проектами, где они участвуют
    project_memberships = db.relationship(
        "ProjectMember",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # а это связь пользователей с проектами гдле заявки
    project_requests = db.relationship(
        "ProjectJoinRequest",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    
    def __repr__(self):
        return f"<User {self.full_name}>"
    
    
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


#модель проекта
class Project(db.Model):

    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    #связь спринтов с проектом
    sprints = db.relationship(
        "Sprint",
        backref="project",
        lazy=True,
        cascade="all, delete-orphan"
    )

    #связь проекта с участниками проекта
    memberships = db.relationship(
        "ProjectMember",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    #связь проекта с заявками на вступлениие
    join_requests = db.relationship(
        "ProjectJoinRequest",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    #фунция для назначения владельца проектом автоматом тимлидом
    def is_teamlead(self, user_id):
        return self.owner_id == user_id

    #проверка, есть ли пользователь в проекте
    def has_member(self, user_id):
        return self.owner_id == user_id or any(
            membership.user_id == user_id for membership in self.memberships
        )

    def __repr__(self):
        return f"<Project {self.name}>"


#ммодель участников проекта
class ProjectMember(db.Model):

    __tablename__ = "project_members"
    
    __table_args__ = (
        db.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )

    id = db.Column(db.Integer, primary_key=True)

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    project = db.relationship("Project", back_populates="memberships")
    
    user = db.relationship("User", back_populates="project_memberships")

#модель заявки на вступление в проект
class ProjectJoinRequest(db.Model):

    __tablename__ = "project_join_requests"
    
    __table_args__ = (
        db.UniqueConstraint("project_id", "user_id", name="uq_project_join_request"),
    )

    id = db.Column(db.Integer, primary_key=True)

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    status = db.Column(db.String(20), nullable=False, default="pending")

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    reviewed_at = db.Column(db.DateTime, nullable=True)

    project = db.relationship("Project", back_populates="join_requests")
    user = db.relationship("User", back_populates="project_requests")


#модель спринтов
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


#модель задач
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


#модель коментов
class Comment(db.Model):

    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)

    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    text = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Comment {self.id}>"


#модель файлов загрузки
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