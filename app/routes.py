import os
import uuid
from datetime import date, datetime
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
from .models import (
    User,
    Project,
    ProjectMember,
    ProjectJoinRequest,
    Sprint,
    Task,
    Comment,
    Attachment,
)
from .services import calculate_sprint_stats
from .validators import (
    parse_date,
    validate_required,
    validate_status,
    validate_story_points,
    validate_sprint_dates,
    ALLOWED_STATUSES,
)

main = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "docx",
    "zip",
}

#проверка файлов
def allowed_file(filename):

    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

#ограничения по ролям
def roles_required(*roles):

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                flash("У вас нет прав для выполнения этого действия", "error")
                return redirect(url_for("main.dashboard"))

            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def can_edit_task_details(task):

    if task.sprint.project.owner_id == current_user.id:
        return True

    if current_user.role == "developer" and task.assignee_id == current_user.id:
        return True

    return False


def can_update_task_status(task):

    return task.sprint.project.has_member(current_user.id)


def can_edit_task(task):

    return can_edit_task_details(task) or can_update_task_status(task)

#только тим лид может создавать задачи
def can_manage_task(task):

    return task.sprint.project.owner_id == current_user.id

#файлы могут загружать все участники команды
def can_upload_to_task(task):

    return task.sprint.project.has_member(current_user.id)

#внутрение данные проекта видны только участникам и админам
def can_view_project(project):

    return current_user.role == "admin" or project.has_member(current_user.id)


def visible_project_ids():

    if current_user.role == "admin":
        return [project_id for (project_id,) in db.session.query(Project.id).all()]

    owned_ids = {
        project_id
        for (project_id,) in db.session.query(Project.id)
        .filter(Project.owner_id == current_user.id)
        .all()
    }
    member_ids = {
        project_id
        for (project_id,) in db.session.query(ProjectMember.project_id)
        .filter(ProjectMember.user_id == current_user.id)
        .all()
    }
    return list(owned_ids | member_ids)


def project_members(project):
    """Возвращает владельца и одобренных участников без дублей."""

    users = {project.owner.id: project.owner}
    users.update(
        {membership.user.id: membership.user for membership in project.memberships}
    )
    return sorted(users.values(), key=lambda user: user.full_name.lower())


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

            validate_required(full_name, "ФИО")
            validate_required(email, "Email")
            validate_required(password, "Пароль")

            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash("Пользователь с таким email уже существует", "error")
                return redirect(url_for("main.register"))

            user = User(
                full_name=full_name,
                email=email,
                password_hash=generate_password_hash(password),
                role="admin" if User.query.count() < 2 else "developer",
            )

            db.session.add(user)
            db.session.commit()

            flash("Регистрация прошла успешно", "success")
            return redirect(url_for("main.login"))

        except ValueError as error:
            flash(str(error), "error")

    return render_template("register.html")


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
        flash("Вы успешно вошли", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@main.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Вы вышли из системы", "success")
    return redirect(url_for("main.index"))


@main.route("/dashboard")
@login_required
def dashboard():
    my_tasks = Task.query.filter_by(assignee_id=current_user.id)
    total_tasks = my_tasks.count()
    completed_tasks = my_tasks.filter(Task.status == "done").count()
    in_progress_tasks = my_tasks.filter(Task.status == "in_progress").count()
    completion_percent = (
        round((completed_tasks / total_tasks) * 100) if total_tasks else 0
    )

    return render_template(
        "dashboard.html",
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        in_progress_tasks=in_progress_tasks,
        completion_percent=completion_percent,
    )


@main.route("/projects")
@login_required
def projects():
    search = request.args.get("search", "").strip()
    query = Project.query

    if search:
        query = query.filter(
            or_(
                Project.name.ilike(f"%{search}%"),
                Project.description.ilike(f"%{search}%"),
            )
        )

    all_projects = query.order_by(Project.created_at.desc()).all()
    requests_by_project = {
        join_request.project_id: join_request
        for join_request in ProjectJoinRequest.query.filter_by(
            user_id=current_user.id
        ).all()
    }
    member_project_ids = {
        membership.project_id
        for membership in ProjectMember.query.filter_by(user_id=current_user.id).all()
    }

    return render_template(
        "projects.html",
        projects=all_projects,
        selected_search=search,
        requests_by_project=requests_by_project,
        member_project_ids=member_project_ids,
    )


@main.route("/projects/create", methods=["GET", "POST"])
@login_required
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
            db.session.flush()
            db.session.add(
                ProjectMember(project_id=project.id, user_id=current_user.id)
            )
            db.session.commit()

            flash("Проект создан", "success")
            return redirect(url_for("main.projects"))

        except ValueError as error:
            flash(str(error), "error")

    return render_template("project_create.html")


@main.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    project = Project.query.get_or_404(project_id)
    is_teamlead = project.is_teamlead(current_user.id)
    is_member = project.has_member(current_user.id)
    can_view_project_data = can_view_project(project)
    project_tasks = []
    if can_view_project_data:
        project_tasks = (
            Task.query.join(Sprint)
            .filter(Sprint.project_id == project.id)
            .order_by(Task.created_at.desc())
            .all()
        )
    completed_tasks = sum(task.status == "done" for task in project_tasks)
    completion_percent = (
        round((completed_tasks / len(project_tasks)) * 100)
        if project_tasks
        else 0
    )
    current_application = ProjectJoinRequest.query.filter_by(
        project_id=project.id,
        user_id=current_user.id,
    ).first()
    pending_requests = []
    if is_teamlead:
        pending_requests = ProjectJoinRequest.query.filter_by(
            project_id=project.id,
            status="pending",
        ).order_by(ProjectJoinRequest.created_at.asc()).all()

    return render_template(
        "project_detail.html",
        project=project,
        members=project_members(project) if can_view_project_data else [],
        current_application=current_application,
        pending_requests=pending_requests,
        is_member=is_member,
        is_teamlead=is_teamlead,
        can_view_project_data=can_view_project_data,
        project_tasks=project_tasks,
        completed_tasks=completed_tasks,
        completion_percent=completion_percent,
    )


@main.route("/projects/<int:project_id>/apply", methods=["POST"])
@login_required
def project_apply(project_id):
    project = Project.query.get_or_404(project_id)

    if project.has_member(current_user.id):
        flash("Вы уже состоите в этом проекте", "error")
        return redirect(url_for("main.project_detail", project_id=project.id))

    join_request = ProjectJoinRequest.query.filter_by(
        project_id=project.id,
        user_id=current_user.id,
    ).first()

    if join_request and join_request.status == "pending":
        flash("Заявка уже отправлена", "error")
    else:
        if join_request:
            join_request.status = "pending"
            join_request.created_at = datetime.utcnow()
            join_request.reviewed_at = None
        else:
            db.session.add(
                ProjectJoinRequest(
                    project_id=project.id,
                    user_id=current_user.id,
                )
            )
        db.session.commit()
        flash("Заявка на вступление отправлена тимлиду", "success")

    return redirect(url_for("main.project_detail", project_id=project.id))


@main.route(
    "/projects/<int:project_id>/requests/<int:request_id>/<decision>",
    methods=["POST"],
)
@login_required
def project_request_review(project_id, request_id, decision):
    project = Project.query.get_or_404(project_id)
    if not project.is_teamlead(current_user.id):
        flash("Только тимлид проекта может рассматривать заявки", "error")
        return redirect(url_for("main.project_detail", project_id=project.id))

    join_request = ProjectJoinRequest.query.filter_by(
        id=request_id,
        project_id=project.id,
    ).first_or_404()

    if join_request.status != "pending":
        flash("Эта заявка уже рассмотрена", "error")
        return redirect(url_for("main.project_detail", project_id=project.id))

    if decision not in {"approve", "reject"}:
        flash("Неизвестное действие", "error")
        return redirect(url_for("main.project_detail", project_id=project.id))

    if decision == "approve":
        membership = ProjectMember.query.filter_by(
            project_id=project.id,
            user_id=join_request.user_id,
        ).first()
        if membership is None:
            db.session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=join_request.user_id,
                )
            )
        join_request.status = "approved"
        message = "Заявка одобрена"
    else:
        join_request.status = "rejected"
        message = "Заявка отклонена"

    join_request.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash(message, "success")
    return redirect(url_for("main.project_detail", project_id=project.id))


@main.route("/sprints")
@login_required
def sprints():
    project_id = request.args.get("project_id", type=int)
    selected_project = None
    query = Sprint.query

    if current_user.role != "admin":
        query = query.filter(Sprint.project_id.in_(visible_project_ids()))

    if project_id is not None:
        selected_project = Project.query.get_or_404(project_id)
        if not can_view_project(selected_project):
            return redirect(
                url_for("main.project_detail", project_id=selected_project.id)
            )
        query = query.filter(Sprint.project_id == selected_project.id)

    all_sprints = query.order_by(Sprint.start_date.desc()).all()
    if selected_project is not None:
        can_create_sprints = selected_project.owner_id == current_user.id
    else:
        can_create_sprints = (
            Project.query.filter_by(owner_id=current_user.id).first() is not None
        )

    return render_template(
        "sprints.html",
        sprints=all_sprints,
        calculate_sprint_stats=calculate_sprint_stats,
        can_create_sprints=can_create_sprints,
        selected_project=selected_project,
    )


@main.route("/sprints/create", methods=["GET", "POST"])
@login_required
def sprint_create():
    projects_list = Project.query.filter_by(owner_id=current_user.id).all()
    context_project_id = request.args.get("project_id", type=int)
    selected_project = None

    if context_project_id is not None:
        selected_project = Project.query.get_or_404(context_project_id)
        if selected_project.owner_id != current_user.id:
            flash("Создавать спринты может только тимлид проекта", "error")
            return redirect(
                url_for("main.project_detail", project_id=selected_project.id)
            )

    if not projects_list:
        flash("Сначала создайте проект — вы станете его тимлидом", "error")
        return redirect(url_for("main.projects"))

    if request.method == "POST":
        try:
            project_id = int(request.form.get("project_id"))
            project = Project.query.filter_by(
                id=project_id,
                owner_id=current_user.id,
            ).first()
            if project is None:
                raise ValueError("Создавать спринты может только тимлид проекта")
            selected_project = project
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

            flash("Спринт создан", "success")
            return redirect(url_for("main.sprints", project_id=project.id))

        except ValueError as error:
            flash(str(error), "error")

    return render_template(
        "sprint_create.html",
        projects=projects_list,
        selected_project=selected_project,
    )


@main.route("/sprints/<int:sprint_id>")
@login_required
def sprint_detail(sprint_id):
    sprint = Sprint.query.get_or_404(sprint_id)
    if not can_view_project(sprint.project):
        return redirect(url_for("main.project_detail", project_id=sprint.project_id))
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
    selected_sprint = None

    if current_user.role != "admin":
        query = query.join(Sprint).filter(
            Sprint.project_id.in_(visible_project_ids())
        )

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
        selected_sprint = Sprint.query.get_or_404(int(sprint_id))
        if not can_view_project(selected_sprint.project):
            return redirect(
                url_for("main.project_detail", project_id=selected_sprint.project_id)
            )
        query = query.filter(Task.sprint_id == selected_sprint.id)

    if assignee_id:
        query = query.filter(Task.assignee_id == int(assignee_id))

    if only_my == "1":
        query = query.filter(Task.assignee_id == current_user.id)

    all_tasks = query.order_by(Task.created_at.desc()).all()

    if current_user.role == "admin":
        sprints_list = Sprint.query.all()
    else:
        sprints_list = Sprint.query.filter(
            Sprint.project_id.in_(visible_project_ids())
        ).all()
    users_list = User.query.all()
    if selected_sprint is not None:
        can_create_tasks = selected_sprint.project.owner_id == current_user.id
    else:
        can_create_tasks = (
            Sprint.query.join(Project)
            .filter(Project.owner_id == current_user.id)
            .first()
            is not None
        )

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
        can_create_tasks=can_create_tasks,
        selected_sprint=selected_sprint,
    )


@main.route("/tasks/create", methods=["GET", "POST"])
@login_required
def task_create():
    sprints_list = (
        Sprint.query.join(Project)
        .filter(Project.owner_id == current_user.id)
        .order_by(Sprint.start_date.desc())
        .all()
    )
    owned_project_ids = [sprint.project_id for sprint in sprints_list]
    users_list = (
        User.query.join(ProjectMember)
        .filter(ProjectMember.project_id.in_(owned_project_ids))
        .distinct()
        .order_by(User.full_name)
        .all()
        if owned_project_ids
        else []
    )
    context_sprint_id = request.args.get("sprint_id", type=int)
    selected_sprint = None

    if context_sprint_id is not None:
        selected_sprint = Sprint.query.get_or_404(context_sprint_id)
        if selected_sprint.project.owner_id != current_user.id:
            flash("Создавать задачи может только тимлид проекта", "error")
            return redirect(
                url_for("main.sprint_detail", sprint_id=selected_sprint.id)
            )
        users_list = project_members(selected_sprint.project)

    if not sprints_list:
        flash("Сначала создайте спринт в своём проекте", "error")
        return redirect(url_for("main.sprints"))

    if request.method == "POST":
        try:
            sprint_id = int(request.form.get("sprint_id"))
            sprint = (
                Sprint.query.join(Project)
                .filter(
                    Sprint.id == sprint_id,
                    Project.owner_id == current_user.id,
                )
                .first()
            )
            if sprint is None:
                raise ValueError("Создавать задачи может только тимлид проекта")
            selected_sprint = sprint

            assignee_id = request.form.get("assignee_id")
            assignee_id = int(assignee_id) if assignee_id else None
            if assignee_id is not None and not sprint.project.has_member(assignee_id):
                raise ValueError("Исполнитель должен быть участником проекта")

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
            return redirect(url_for("main.tasks", sprint_id=sprint.id))

        except ValueError as error:
            flash(str(error), "error")

    return render_template(
        "task_create.html",
        sprints=sprints_list,
        users=users_list,
        statuses=ALLOWED_STATUSES,
        selected_sprint=selected_sprint,
    )


@main.route("/tasks/<int:task_id>")
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)

    if not can_view_project(task.sprint.project):
        return redirect(
            url_for("main.project_detail", project_id=task.sprint.project_id)
        )

    return render_template(
        "task_detail.html",
        task=task,
        can_edit=can_edit_task(task),
        can_manage=can_manage_task(task),
        can_upload=can_upload_to_task(task),
    )


@main.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def task_edit(task_id):
    task = Task.query.get_or_404(task_id)

    if not can_edit_task(task):
        flash("У вас нет прав редактировать эту задачу", "error")
        return redirect(url_for("main.task_detail", task_id=task.id))

    manages_task = can_manage_task(task)
    can_edit_details = can_edit_task_details(task)
    if manages_task:
        sprints_list = (
            Sprint.query.join(Project)
            .filter(Project.owner_id == current_user.id)
            .all()
        )
    else:
        sprints_list = [task.sprint]
    users_list = project_members(task.sprint.project)

    if request.method == "POST":
        try:
            if manages_task:
                sprint_id = int(request.form.get("sprint_id"))
                selected_sprint = (
                    Sprint.query.join(Project)
                    .filter(
                        Sprint.id == sprint_id,
                        Project.owner_id == current_user.id,
                    )
                    .first()
                )
                if selected_sprint is None:
                    raise ValueError("Можно выбрать только спринт своего проекта")

                assignee_id = request.form.get("assignee_id")
                assignee_id = int(assignee_id) if assignee_id else None
                if (
                    assignee_id is not None
                    and not selected_sprint.project.has_member(assignee_id)
                ):
                    raise ValueError("Исполнитель должен быть участником проекта")

                task.sprint_id = selected_sprint.id
                task.assignee_id = assignee_id

            task.status = request.form.get("status", task.status)
            validate_status(task.status)

            if can_edit_details:
                task.title = request.form.get("title", "").strip()
                task.description = request.form.get("description", "").strip()
                task.story_points = validate_story_points(request.form.get("story_points"))
                task.deadline = parse_date(request.form.get("deadline"))

                validate_required(task.title, "Название задачи")

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
        can_manage=manages_task,
        can_edit_details=can_edit_details,
    )


@main.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def task_delete(task_id):
    task = Task.query.get_or_404(task_id)

    if not can_manage_task(task):
        flash("Удалить задачу может только тимлид проекта", "error")
        return redirect(url_for("main.task_detail", task_id=task.id))

    db.session.delete(task)
    db.session.commit()

    flash("Задача удалена", "success")
    return redirect(url_for("main.tasks"))


@main.route("/tasks/<int:task_id>/comments", methods=["POST"])
@login_required
def comment_create(task_id):
    task = Task.query.get_or_404(task_id)

    if not can_view_project(task.sprint.project):
        return redirect(
            url_for("main.project_detail", project_id=task.sprint.project_id)
        )

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

    if not can_upload_to_task(task):
        flash("Загружать файлы могут только участники команды проекта", "error")
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

    if not can_view_project(attachment.task.sprint.project):
        return redirect(
            url_for(
                "main.project_detail",
                project_id=attachment.task.sprint.project_id,
            )
        )

    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        attachment.filename,
        as_attachment=True,
        download_name=attachment.original_filename,
    )


@main.route("/reports")
@login_required
def reports():
    if current_user.role == "admin":
        all_sprints = Sprint.query.all()
    else:
        all_sprints = (
            Sprint.query.join(Project)
            .filter(Project.owner_id == current_user.id)
            .all()
        )

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


@main.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@roles_required("admin")
def user_delete(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("Нельзя удалить собственный аккаунт", "error")
        return redirect(url_for("main.users"))

    if user.role == "admin":
        flash("Администраторов нельзя удалять через эту страницу", "error")
        return redirect(url_for("main.users"))

    if user.projects:
        flash("Нельзя удалить тимлида: сначала передайте или удалите его проекты", "error")
        return redirect(url_for("main.users"))

    attachment_filenames = [
        filename
        for (filename,) in db.session.query(Attachment.filename)
        .filter(Attachment.user_id == user.id)
        .all()
    ]

    Task.query.filter_by(assignee_id=user.id).update(
        {Task.assignee_id: None},
        synchronize_session=False,
    )
    Comment.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    Attachment.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    ProjectMember.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    ProjectJoinRequest.query.filter_by(user_id=user.id).delete(
        synchronize_session=False
    )

    db.session.delete(user)
    db.session.commit()

    for filename in attachment_filenames:
        file_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"],
            os.path.basename(filename),
        )
        if os.path.isfile(file_path):
            os.remove(file_path)

    flash("Пользователь удалён", "success")
    return redirect(url_for("main.users"))
