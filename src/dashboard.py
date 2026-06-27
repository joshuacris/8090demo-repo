"""Dashboard endpoint — now with Redis caching per section."""

from fastapi import APIRouter, Depends, HTTPException
from .cache import get_cached, set_cached
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timedelta
from .models import Task, Sprint, User, Team, TaskStatus
from .database import get_db

router = APIRouter()


@router.get("/api/dashboard/{team_id}")
def get_dashboard(team_id: int, db: Session = Depends(get_db)):
    """Returns full dashboard payload. Cached per-section with Redis."""

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # --- Check cache for each section, only query DB for misses ---
    cached_status = get_cached(team_id, "status_breakdown")
    cached_velocity = get_cached(team_id, "velocity")
    cached_cycle = get_cached(team_id, "cycle_time")
    cached_workload = get_cached(team_id, "workload")
    cached_overdue = get_cached(team_id, "overdue")

    # Current sprint
    now = datetime.utcnow()
    current_sprint = (
        db.query(Sprint)
        .filter(Sprint.team_id == team_id, Sprint.start_date <= now, Sprint.end_date >= now)
        .first()
    )

    # --- Task status breakdown ---
    if cached_status is not None:
        status_breakdown = cached_status
    else:
        status_counts = (
            db.query(Task.status, func.count(Task.id))
            .join(Sprint, Task.sprint_id == Sprint.id)
            .filter(Sprint.team_id == team_id)
            .group_by(Task.status)
            .all()
        )
        status_breakdown = {str(s): c for s, c in status_counts}
        set_cached(team_id, "status_breakdown", status_breakdown)

    # --- Velocity over last 5 sprints ---
    if cached_velocity is not None:
        velocity = cached_velocity
    else:
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
                db.query(func.sum(Task.story_points)).filter(Task.sprint_id == sprint.id).scalar()
                or 0
            )
            velocity.append(
                {"sprint": sprint.name, "completed": completed_points, "total": total_points}
            )
        set_cached(team_id, "velocity", velocity)

    # --- Cycle time (avg hours from in_progress to done, last 30 days) ---
    if cached_cycle is not None:
        avg_cycle_hours = cached_cycle
    else:
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
            avg_cycle_hours = round((total_cycle / len(cycle_time_tasks)) / 3600, 1)
        else:
            avg_cycle_hours = 0
        set_cached(team_id, "cycle_time", avg_cycle_hours)

    # --- Overdue tasks ---
    if cached_overdue is not None:
        overdue = cached_overdue
    else:
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
        set_cached(team_id, "overdue", overdue)

    # --- Per-member workload ---
    if cached_workload is not None:
        member_workload = cached_workload
    else:
        workload_rows = (
            db.query(User.username, func.count(Task.id), func.sum(Task.story_points))
            .join(Task, User.id == Task.assignee_id)
            .join(Sprint, Task.sprint_id == Sprint.id)
            .filter(
                Sprint.team_id == team_id,
                Task.status.in_(["todo", "in_progress", "in_review"]),
            )
            .group_by(User.username)
            .all()
        )
        member_workload = [
            {"member": m, "active_tasks": c, "story_points": sp}
            for m, c, sp in workload_rows
        ]
        set_cached(team_id, "workload", member_workload)

    return {
        "team": team.name,
        "current_sprint": current_sprint.name if current_sprint else None,
        "status_breakdown": status_breakdown,
        "velocity": velocity,
        "avg_cycle_time_hours": avg_cycle_hours,
        "overdue_tasks": overdue,
        "member_workload": member_workload,
    }
