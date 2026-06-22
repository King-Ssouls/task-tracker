import os
import uuid
from datetime import date
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    current_app,
    send_from_directory,
)
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from .extensions import db
from .models import User, Project, Sprint, Task, Comment, Attachment
from .services import calculate_sprint_stats
from .validators import (
    parse_date,
    validate_required,
    validate_role,
    validate_status,
    validate_story_points,
    validate_sprint_dates,
    ALLOWED_STATUSES,
    ALLOWED_ROLES,
)

main = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "docx",
    "xlsx",
    "txt",
}

#проверка расширения файлов
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


#ограничения доступа по ролям
def roles_required(*roles):
    
    def decorator(view_func):
        
        @wraps(view_func)
        
        def wrapper(*args, **kwargs):
            
            if current_user.role not in roles:
                flash("У вас нет прав для этого действия", "error")
                return redirect(url_for("main.dashboard"))

            return view_func(*args, **kwargs)

        return wrapper

    return decorator


#Проверка на доступ пользователя к редактированию задач
def can_edit_task(task):

    if current_user.role in ["admin", "teamlead"]:
        return True

    if current_user.role == "developer" and task.assignee_id == current_user.id:
        return True

    return False



@main.route("/")
def index():
    return render_template("index.html")



@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            role = request.form.get("role", "developer")

            validate_required(full_name, "ФИО")
            validate_required(email, "Email")
            validate_required(password, "Пароль")
            validate_role(role)

            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash("Пользователь с таким email уже существует", "error")
                return redirect(url_for("main.register"))

            user = User(
                full_name=full_name,
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
            )

            db.session.add(user)
            db.session.commit()

            flash("Регистрация прошла успешно", "success")
            return redirect(url_for("main.login"))

        except ValueError as error:
            flash(str(error), "error")

    return render_template("register.html", roles=ALLOWED_ROLES)


@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash("Неверный email или пароль", "error")
            return redirect(url_for("main.login"))

        login_user(user)
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@main.route("/dashboard")
@login_required
def dashboard():
    projects_count = Project.query.count()
    sprints_count = Sprint.query.count()
    tasks_count = Task.query.count()
    done_tasks_count = Task.query.filter_by(status="done").count()

    return render_template(
        "dashboard.html",
        projects_count=projects_count,
        sprints_count=sprints_count,
        tasks_count=tasks_count,
        done_tasks_count=done_tasks_count,
    )


@main.route("/projects")
@login_required
def projects():
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template("projects.html", projects=all_projects)


@main.route("/projects/create", methods=["GET", "POST"])
@login_required
@roles_required("admin", "teamlead")
def project_create():
    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()

            validate_required(name, "Название проекта")

            project = Project(
                name=name,
                description=description,
                owner_id=current_user.id,
            )

            db.session.add(project)
            db.session.commit()

            return redirect(url_for("main.projects"))

        except ValueError as error:
            flash(str(error), "error")

    return render_template("project_create.html")


@main.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    return render_template("project_detail.html", project=project)


@main.route("/sprints")
@login_required
def sprints():
    all_sprints = Sprint.query.order_by(Sprint.start_date.desc()).all()

    return render_template(
        "sprints.html",
        sprints=all_sprints,
        calculate_sprint_stats=calculate_sprint_stats,
    )


@main.route("/sprints/create", methods=["GET", "POST"])
@login_required
@roles_required("admin", "teamlead")
def sprint_create():
    projects_list = Project.query.all()

    if request.method == "POST":
        try:
            project_id = int(request.form.get("project_id"))
            name = request.form.get("name", "").strip()
            start_date = parse_date(request.form.get("start_date"))
            end_date = parse_date(request.form.get("end_date"))
            planned_points = int(request.form.get("planned_points", 0))

            validate_required(name, "Название спринта")
            validate_sprint_dates(start_date, end_date)

            sprint = Sprint(
                project_id=project_id,
                name=name,
                start_date=start_date,
                end_date=end_date,
                planned_points=planned_points,
            )

            db.session.add(sprint)
            db.session.commit()

            return redirect(url_for("main.sprints"))

        except ValueError as error:
            flash(str(error), "error")

    return render_template("sprint_create.html", projects=projects_list)


@main.route("/sprints/<int:sprint_id>")
@login_required
def sprint_detail(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    stats = calculate_sprint_stats(sprint)

    return render_template("sprint_detail.html", sprint=sprint, stats=stats)


@main.route("/tasks")
@login_required
def tasks():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "")
    sprint_id = request.args.get("sprint_id", "")
    assignee_id = request.args.get("assignee_id", "")
    only_my = request.args.get("only_my", "")

    query = Task.query

    if search:
        query = query.filter(
            or_(
                Task.title.ilike(f"%{search}%"),
                Task.description.ilike(f"%{search}%"),
            )
        )

    if status:
        query = query.filter(Task.status == status)

    if sprint_id:
        query = query.filter(Task.sprint_id == int(sprint_id))

    if assignee_id:
        query = query.filter(Task.assignee_id == int(assignee_id))

    if only_my == "1":
        query = query.filter(Task.assignee_id == current_user.id)

    all_tasks = query.order_by(Task.created_at.desc()).all()

    sprints_list = Sprint.query.all()
    users_list = User.query.all()

    return render_template(
        "tasks.html",
        tasks=all_tasks,
        statuses=ALLOWED_STATUSES,
        sprints=sprints_list,
        users=users_list,
        selected_search=search,
        selected_status=status,
        selected_sprint_id=sprint_id,
        selected_assignee_id=assignee_id,
        selected_only_my=only_my,
    )


@main.route("/tasks/create", methods=["GET", "POST"])
@login_required
@roles_required("admin", "teamlead")
def task_create():
    sprints_list = Sprint.query.all()
    users_list = User.query.all()

    if request.method == "POST":
        try:
            sprint_id = int(request.form.get("sprint_id"))
            assignee_id = request.form.get("assignee_id")
            assignee_id = int(assignee_id) if assignee_id else None

            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            status = request.form.get("status", "new")
            story_points = validate_story_points(request.form.get("story_points"))
            deadline = parse_date(request.form.get("deadline"))

            validate_required(title, "Название задачи")
            validate_status(status)

            completed_at = None
            if status == "done":
                completed_at = date.today()

            task = Task(
                sprint_id=sprint_id,
                assignee_id=assignee_id,
                title=title,
                description=description,
                status=status,
                story_points=story_points,
                deadline=deadline,
                completed_at=completed_at,
            )

            db.session.add(task)
            db.session.commit()

            flash("Задача создана", "success")
            return redirect(url_for("main.tasks"))

        except ValueError as error:
            flash(str(error), "error")

    return render_template(
        "task_create.html",
        sprints=sprints_list,
        users=users_list,
        statuses=ALLOWED_STATUSES,
    )


@main.route("/tasks/<int:task_id>")
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)

    return render_template(
        "task_detail.html",
        task=task,
        can_edit=can_edit_task(task),
    )


@main.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def task_edit(task_id):
    task = Task.query.get_or_404(task_id)

    if not can_edit_task(task):
        flash("У вас нет прав редактировать эту задачу", "error")
        return redirect(url_for("main.task_detail", task_id=task.id))

    sprints_list = Sprint.query.all()
    users_list = User.query.all()

    if request.method == "POST":
        try:
            task.sprint_id = int(request.form.get("sprint_id"))

            assignee_id = request.form.get("assignee_id")
            task.assignee_id = int(assignee_id) if assignee_id else None

            task.title = request.form.get("title", "").strip()
            task.description = request.form.get("description", "").strip()
            task.status = request.form.get("status", "new")
            task.story_points = validate_story_points(request.form.get("story_points"))
            task.deadline = parse_date(request.form.get("deadline"))

            validate_required(task.title, "Название задачи")
            validate_status(task.status)

            if task.status == "done" and task.completed_at is None:
                task.completed_at = date.today()

            if task.status != "done":
                task.completed_at = None

            db.session.commit()

            flash("Задача обновлена", "success")
            return redirect(url_for("main.task_detail", task_id=task.id))

        except ValueError as error:
            flash(str(error), "error")

    return render_template(
        "task_edit.html",
        task=task,
        sprints=sprints_list,
        users=users_list,
        statuses=ALLOWED_STATUSES,
    )


@main.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
@roles_required("admin", "teamlead")
def task_delete(task_id):
    task = Task.query.get_or_404(task_id)

    db.session.delete(task)
    db.session.commit()

    flash("Задача удалена", "success")
    return redirect(url_for("main.tasks"))


@main.route("/tasks/<int:task_id>/comments", methods=["POST"])
@login_required
def comment_create(task_id):
    task = Task.query.get_or_404(task_id)

    try:
        text = request.form.get("text", "").strip()
        validate_required(text, "Комментарий")

        comment = Comment(
            task_id=task.id,
            user_id=current_user.id,
            text=text,
        )

        db.session.add(comment)
        db.session.commit()

        flash("Комментарий добавлен", "success")

    except ValueError as error:
        flash(str(error), "error")

    return redirect(url_for("main.task_detail", task_id=task.id))


@main.route("/tasks/<int:task_id>/upload", methods=["POST"])
@login_required
def upload_file(task_id):
    task = Task.query.get_or_404(task_id)

    if not can_edit_task(task):
        flash("У вас нет прав загружать файлы к этой задаче", "error")
        return redirect(url_for("main.task_detail", task_id=task.id))

    uploaded_file = request.files.get("file")

    if not uploaded_file or uploaded_file.filename == "":
        flash("Файл не выбран", "error")
        return redirect(url_for("main.task_detail", task_id=task.id))

    if not allowed_file(uploaded_file.filename):
        flash("Недопустимый тип файла", "error")
        return redirect(url_for("main.task_detail", task_id=task.id))

    original_filename = secure_filename(uploaded_file.filename)
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"

    file_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_filename)
    uploaded_file.save(file_path)

    attachment = Attachment(
        task_id=task.id,
        user_id=current_user.id,
        filename=unique_filename,
        original_filename=original_filename,
    )

    db.session.add(attachment)
    db.session.commit()

    flash("Файл загружен", "success")
    return redirect(url_for("main.task_detail", task_id=task.id))


@main.route("/attachments/<int:attachment_id>/download")
@login_required
def download_file(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        attachment.filename,
        as_attachment=True,
        download_name=attachment.original_filename,
    )


@main.route("/reports")
@login_required
@roles_required("admin", "teamlead")
def reports():
    all_sprints = Sprint.query.all()

    report_items = []

    for sprint in all_sprints:
        stats = calculate_sprint_stats(sprint)

        report_items.append(
            {
                "sprint": sprint,
                "stats": stats,
            }
        )

    return render_template("reports.html", report_items=report_items)


@main.route("/users")
@login_required
@roles_required("admin")
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=all_users)