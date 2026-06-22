from datetime import date, datetime

ALLOWED_STATUSES = ["new", "in_progress", "review", "done"]
ALLOWED_ROLES = ["admin", "teamlead", "developer", "manager"]

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

    if points < 1 or points > 5:
        raise ValueError("Story points должны быть от 1 до 5")

    return points


#валидация даты спринта
def validate_sprint_dates(start_date, end_date):
    if start_date is None or end_date is None:
        raise ValueError("Укажите даты спринта")

    today = date.today()

    if start_date < today:
        raise ValueError("Дата начала спринта не может быть раньше текущего дня")

    if end_date < today:
        raise ValueError("Дата окончания спринта не может быть раньше текущего дня")

    if start_date > end_date:
        raise ValueError("Дата окончания не может быть раньше даты начала")
