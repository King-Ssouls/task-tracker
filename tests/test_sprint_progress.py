from app import create_app
from app.extensions import db
from app.models import Project, ProjectJoinRequest, ProjectMember, Sprint, Task, User


def make_app():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        db.create_all()
    return app


def register(client, name, email):
    return client.post(
        "/register",
        data={"full_name": name, "email": email, "password": "password"},
        follow_redirects=True,
    )


def login(client, email):
    return client.post(
        "/login",
        data={"email": email, "password": "password"},
        follow_redirects=True,
    )


def test_first_two_users_are_admins_and_role_cannot_be_selected():
    app = make_app()
    client = app.test_client()

    register(client, "First", "first@example.com")
    register(client, "Second", "second@example.com")
    client.post(
        "/register",
        data={
            "full_name": "Third",
            "email": "third@example.com",
            "password": "password",
            "role": "admin",
        },
    )

    with app.app_context():
        users = User.query.order_by(User.id).all()
        assert [user.role for user in users] == ["admin", "admin", "developer"]


def test_join_request_and_project_owner_permissions():
    app = make_app()
    client = app.test_client()

    register(client, "Lead", "lead@example.com")
    register(client, "Admin Viewer", "admin-viewer@example.com")
    login(client, "lead@example.com")
    client.post(
        "/projects/create",
        data={"name": "Apollo", "description": "Searchable project"},
    )
    client.get("/logout")

    register(client, "Member", "member@example.com")
    login(client, "member@example.com")

    with app.app_context():
        project = Project.query.one()
        project_id = project.id

    restricted_page = client.get(f"/projects/{project_id}").get_data(as_text=True)
    assert "Apollo" in restricted_page
    assert "Lead" in restricted_page
    assert "Подать заявку" in restricted_page
    assert "Команда" not in restricted_page
    assert "Спринты проекта" not in restricted_page
    assert "Задачи проекта" not in restricted_page

    client.post(
        "/sprints/create",
        data={
            "project_id": project_id,
            "name": "Forbidden",
            "start_date": "2026-06-22",
            "end_date": "2026-06-29",
            "planned_points": 10,
        },
    )
    client.post(f"/projects/{project_id}/apply")

    with app.app_context():
        assert Sprint.query.count() == 0
        join_request = ProjectJoinRequest.query.one()
        assert join_request.status == "pending"
        request_id = join_request.id

    client.get("/logout")
    login(client, "lead@example.com")
    client.post(
        f"/projects/{project_id}/requests/{request_id}/approve",
        follow_redirects=True,
    )

    with app.app_context():
        join_request = db.session.get(ProjectJoinRequest, request_id)
        member = User.query.filter_by(email="member@example.com").one()
        member_id = member.id
        assert join_request.status == "approved"
        assert ProjectMember.query.filter_by(
            project_id=project_id, user_id=member.id
        ).one()

    client.post(
        "/sprints/create",
        data={
            "project_id": project_id,
            "name": "Sprint 1",
            "start_date": "2026-06-22",
            "end_date": "2026-06-29",
            "planned_points": 10,
        },
    )
    with app.app_context():
        sprint_id = Sprint.query.one().id

    sprint_page = client.get(f"/sprints/{sprint_id}").get_data(as_text=True)
    assert f"/tasks/create?sprint_id={sprint_id}" in sprint_page
    assert f"/tasks?sprint_id={sprint_id}" in sprint_page

    contextual_task_form = client.get(
        f"/tasks/create?sprint_id={sprint_id}"
    ).get_data(as_text=True)
    assert '<select name="sprint_id"' not in contextual_task_form
    assert f'<input type="hidden" name="sprint_id" value="{sprint_id}">' in contextual_task_form

    client.post(
        f"/tasks/create?sprint_id={sprint_id}",
        data={
            "sprint_id": sprint_id,
            "assignee_id": member_id,
            "title": "Owner-created task",
            "description": "",
            "status": "done",
            "story_points": 3,
            "deadline": "",
        },
    )
    with app.app_context():
        task = Task.query.one()
        assert task.assignee_id == member_id
        task_id = task.id

    project_page = client.get(f"/projects/{project_id}").get_data(as_text=True)
    assert f"/sprints/create?project_id={project_id}" in project_page
    assert f"/sprints?project_id={project_id}" in project_page
    assert "Выполнено 1 из 1 задач" in project_page
    assert "100%" in project_page

    contextual_form = client.get(
        f"/sprints/create?project_id={project_id}"
    ).get_data(as_text=True)
    assert '<select name="project_id"' not in contextual_form
    assert f'<input type="hidden" name="project_id" value="{project_id}">' in contextual_form

    client.post(
        "/projects/create",
        data={"name": "Zeus", "description": "Second project"},
    )
    with app.app_context():
        second_project_id = Project.query.filter_by(name="Zeus").one().id

    client.post(
        f"/sprints/create?project_id={second_project_id}",
        data={
            "project_id": second_project_id,
            "name": "Other project sprint",
            "start_date": "2026-07-01",
            "end_date": "2026-07-08",
            "planned_points": 5,
        },
    )
    with app.app_context():
        second_sprint_id = Sprint.query.filter_by(name="Other project sprint").one().id

    client.post(
        f"/tasks/create?sprint_id={second_sprint_id}",
        data={
            "sprint_id": second_sprint_id,
            "assignee_id": "",
            "title": "Other sprint task",
            "description": "",
            "status": "new",
            "story_points": 2,
            "deadline": "",
        },
    )
    filtered_sprints = client.get(
        f"/sprints?project_id={project_id}"
    ).get_data(as_text=True)
    assert "Sprint 1" in filtered_sprints
    assert "Other project sprint" not in filtered_sprints

    filtered_tasks = client.get(
        f"/tasks?sprint_id={sprint_id}"
    ).get_data(as_text=True)
    assert "Owner-created task" in filtered_tasks
    assert "Other sprint task" not in filtered_tasks

    client.get("/logout")
    login(client, "member@example.com")
    dashboard_page = client.get("/dashboard").get_data(as_text=True)
    assert "Статистика выполнения задач" in dashboard_page
    assert "100%" in dashboard_page
    upload_response = client.post(
        f"/tasks/{task_id}/upload",
        follow_redirects=True,
    )
    assert "Файл не выбран" in upload_response.get_data(as_text=True)

    response = client.get("/projects?search=Apollo")
    assert "Apollo" in response.get_data(as_text=True)

    member_project_page = client.get(
        f"/projects/{project_id}"
    ).get_data(as_text=True)
    assert "Команда" in member_project_page
    assert "Owner-created task" in member_project_page

    client.get("/logout")
    login(client, "admin-viewer@example.com")
    admin_project_page = client.get(
        f"/projects/{project_id}"
    ).get_data(as_text=True)
    assert "Просмотр проекта как администратор" in admin_project_page
    assert "Команда" in admin_project_page
    assert "Owner-created task" in admin_project_page

    register(client, "Outsider", "outsider@example.com")
    client.get("/logout")
    login(client, "outsider@example.com")

    outsider_project_page = client.get(
        f"/projects/{project_id}"
    ).get_data(as_text=True)
    assert "Подать заявку" in outsider_project_page
    assert "Команда" not in outsider_project_page
    assert "Owner-created task" not in outsider_project_page

    assert client.get(f"/tasks/{task_id}").status_code == 302
    assert client.get(f"/sprints/{sprint_id}").status_code == 302
    assert "Owner-created task" not in client.get("/tasks").get_data(as_text=True)


def test_admin_can_delete_regular_user():
    app = make_app()
    client = app.test_client()

    register(client, "Admin One", "admin-one@example.com")
    register(client, "Admin Two", "admin-two@example.com")
    register(client, "Delete Me", "delete-me@example.com")

    login(client, "admin-one@example.com")
    with app.app_context():
        user_id = User.query.filter_by(email="delete-me@example.com").one().id

    response = client.post(f"/users/{user_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    with app.app_context():
        assert User.query.filter_by(email="delete-me@example.com").first() is None
