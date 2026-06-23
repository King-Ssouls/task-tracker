from datetime import datetime

ALLOWED_STATUSES = ["new", "in_progress", "review", "done"]
ALLOWED_ROLES = ["admin", "developer"]

#преобразование строку формата yyyy-mm-dd в дату
def parse_date(date_string):

    if not date_string:
        return None

    try:
        return datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Некорректный формат даты")


#функция на проверку незаполненных полей
def validate_required(value, field_name):
    if not value or not value.strip():
        raise ValueError(f"Поле '{field_name}' обязательно для заполнения")


#валидация ролей пользоваетеля
def validate_role(role):
    if role not in ALLOWED_ROLES:
        raise ValueError("Некорректная роль пользователя")


#валидация на проверку статуса задачи
def validate_status(status):
    if status not in ALLOWED_STATUSES:
        raise ValueError("Некорректный статус задачи")


#валидация сложности задачи
def validate_story_points(points):
    try:
        points = int(points)
    except ValueError:
        raise ValueError("Story points должны быть числом")

    if points < 1 or points > 100:
        raise ValueError("Story points должны быть от 1 до 100")

    return points


#валидация даты спринта
def validate_sprint_dates(start_date, end_date):
    if start_date is None or end_date is None:
        raise ValueError("Укажите даты спринта")

    if start_date > end_date:
        raise ValueError("Дата окончания не может быть раньше даты начала")