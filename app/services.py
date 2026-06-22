from datetime import date

#для функция для отслеживаания процесса спринта
def calculate_sprint_stats(sprint):
    tasks = sprint.tasks

    total_points = sum(task.story_points for task in tasks)

    completed_tasks = [task for task in tasks if task.status == "done"]
    completed_points = sum(task.story_points for task in completed_tasks)

    if total_points == 0:
        actual_progress = 0
    else:
        actual_progress = round((completed_points / total_points) * 100, 2)

    today = date.today()

    total_days = (sprint.end_date - sprint.start_date).days + 1
    passed_days = (today - sprint.start_date).days + 1

    if total_days <= 0:
        planned_progress = 100
    elif today < sprint.start_date:
        planned_progress = 0
    elif today > sprint.end_date:
        planned_progress = 100
    else:
        planned_progress = round((passed_days / total_days) * 100, 2)

    deviation = round(actual_progress - planned_progress, 2)

    velocity = completed_points

    if len(tasks) == 0:
        on_time_percent = 0
    else:
        completed_on_time = 0

        for task in completed_tasks:
            if task.deadline and task.completed_at and task.completed_at <= task.deadline:
                completed_on_time += 1

        on_time_percent = round((completed_on_time / len(tasks)) * 100, 2)

    return {
        "total_points": total_points,
        "completed_points": completed_points,
        "actual_progress": actual_progress,
        "planned_progress": planned_progress,
        "deviation": deviation,
        "velocity": velocity,
        "total_tasks": len(tasks),
        "completed_tasks": len(completed_tasks),
        "on_time_percent": on_time_percent,
    }