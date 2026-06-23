from datetime import date

from app.services import calculate_sprint_stats


class FakeTask:
    def __init__(self, status, story_points, deadline=None, completed_at=None):
        self.status = status
        self.story_points = story_points
        self.deadline = deadline
        self.completed_at = completed_at


class FakeSprint:
    def __init__(self, start_date, end_date, tasks):
        self.start_date = start_date
        self.end_date = end_date
        self.tasks = tasks


def test_sprint_progress():
    sprint = FakeSprint(
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 10),
        tasks=[
            FakeTask(status="done", story_points=5),
            FakeTask(status="new", story_points=5),
        ],
    )

    stats = calculate_sprint_stats(sprint)

    assert stats["total_points"] == 10
    assert stats["completed_points"] == 5
    assert stats["actual_progress"] == 50
    assert stats["velocity"] == 5
