"""Dashboard endpoint — the slow one. Joins 4 tables, computes aggregations on every request."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta
from .models import Task, Sprint, User, Team, TaskStatus
from .database import get_db

router = APIRouter()


@router.get("/api/dashboard/{team_id}")
def get_dashboard(team_id: int, db: Session = Depends(get_db)):
    """Returns full dashboard payload. Currently 4–8s on large teams."""

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Current sprint
    now = datetime.utcnow()
    current_sprint = (
        db.query(Sprint)
        .filter(Sprint.team_id == team_id, Sprint.start_date <= now, Sprint.end_date >= now)
        .first()
    )

    # --- EXPENSIVE: task status breakdown (joins tasks + sprint + users) ---
    status_counts = (
        db.query(Task.status, func.count(Task.id))
        .join(Sprint, Task.sprint_id == Sprint.id)
        .filter(Sprint.team_id == team_id)
        .group_by(Task.status)
        .all()
    )

    # --- EXPENSIVE: velocity over last 5 sprints ---
    recent_sprints = (
        db.query(Sprint)
        .filter(Sprint.team_id == team_id)
        .order_by(Sprint.end_date.desc())
        .limit(5)
        .all()
    )

    velocity = []
    for sprint in recent_sprints:
        completed_points = (
            db.query(func.sum(Task.story_points))
            .filter(Task.sprint_id == sprint.id, Task.status == TaskStatus.DONE)
            .scalar()
            or 0
        )
        total_points = (
            db.query(func.sum(Task.story_points)).filter(Task.sprint_id == sprint.id).scalar() or 0
        )
        velocity.append(
            {"sprint": sprint.name, "completed": completed_points, "total": total_points}
        )

    # --- EXPENSIVE: cycle time (avg time from in_progress to done, last 30 days) ---
    thirty_days_ago = now - timedelta(days=30)
    cycle_time_tasks = (
        db.query(Task)
        .join(Sprint, Task.sprint_id == Sprint.id)
        .filter(
            Sprint.team_id == team_id,
            Task.status == TaskStatus.DONE,
            Task.completed_at >= thirty_days_ago,
        )
        .all()
    )

    if cycle_time_tasks:
        total_cycle = sum(
            (t.completed_at - t.updated_at).total_seconds()
            for t in cycle_time_tasks
            if t.completed_at and t.updated_at
        )
        avg_cycle_hours = (total_cycle / len(cycle_time_tasks)) / 3600
    else:
        avg_cycle_hours = 0

    # --- EXPENSIVE: overdue tasks ---
    overdue = (
        db.query(Task)
        .join(Sprint, Task.sprint_id == Sprint.id)
        .filter(
            Sprint.team_id == team_id,
            Sprint.end_date < now,
            Task.status != TaskStatus.DONE,
        )
        .count()
    )

    # --- EXPENSIVE: per-member workload ---
    member_workload = (
        db.query(User.username, func.count(Task.id), func.sum(Task.story_points))
        .join(Task, User.id == Task.assignee_id)
        .join(Sprint, Task.sprint_id == Sprint.id)
        .filter(Sprint.team_id == team_id, Task.status.in_(["todo", "in_progress", "in_review"]))
        .group_by(User.username)
        .all()
    )

    return {
        "team": team.name,
        "current_sprint": current_sprint.name if current_sprint else None,
        "status_breakdown": {str(s): c for s, c in status_counts},
        "velocity": velocity,
        "avg_cycle_time_hours": round(avg_cycle_hours, 1),
        "overdue_tasks": overdue,
        "member_workload": [
            {"member": m, "active_tasks": c, "story_points": sp} for m, c, sp in member_workload
        ],
    }
