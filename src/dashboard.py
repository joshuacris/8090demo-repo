"""Dashboard endpoint — optimized with materialized views and denormalized team_id."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, text
from datetime import datetime, timedelta
from .models import Task, Sprint, User, Team, TaskStatus
from .database import get_db

router = APIRouter()


@router.get("/api/dashboard/{team_id}")
def get_dashboard(team_id: int, db: Session = Depends(get_db)):
    """Returns full dashboard payload. Optimized via materialized view + denormalized team_id."""

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

    # --- FAST: status breakdown + velocity from materialized view ---
    stats = db.execute(
        text("""
            SELECT todo_count, in_progress_count, in_review_count, done_count, blocked_count,
                   completed_points, total_points, avg_cycle_time_hours,
                   sprint_name
            FROM mv_team_dashboard_stats
            WHERE team_id = :tid
            ORDER BY end_date DESC
            LIMIT 5
        """),
        {"tid": team_id},
    ).fetchall()

    # Current sprint status breakdown (most recent)
    current = stats[0] if stats else None
    status_breakdown = {
        "todo": current.todo_count if current else 0,
        "in_progress": current.in_progress_count if current else 0,
        "in_review": current.in_review_count if current else 0,
        "done": current.done_count if current else 0,
        "blocked": current.blocked_count if current else 0,
    }

    # --- FAST: velocity from same materialized view (already fetched) ---
    velocity = [
        {"sprint": s.sprint_name, "completed": s.completed_points, "total": s.total_points}
        for s in stats
    ]

    # --- FAST: cycle time from materialized view ---
    avg_cycle_hours = (
        round(current.avg_cycle_time_hours, 1)
        if current and current.avg_cycle_time_hours
        else 0
    )

    # --- Overdue tasks (still hits DB but uses denormalized team_id — no join) ---
    overdue = (
        db.query(Task)
        .filter(
            Task.team_id == team_id,
            Task.sprint.has(Sprint.end_date < now),
            Task.status != TaskStatus.DONE,
        )
        .count()
    )

    # --- Per-member workload (still ORM but uses denormalized team_id — no join) ---
    member_workload = (
        db.query(User.username, func.count(Task.id), func.sum(Task.story_points))
        .join(Task, User.id == Task.assignee_id)
        .filter(Task.team_id == team_id, Task.status.in_(["todo", "in_progress", "in_review"]))
        .group_by(User.username)
        .all()
    )

    return {
        "team": team.name,
        "current_sprint": current_sprint.name if current_sprint else None,
        "status_breakdown": status_breakdown,
        "velocity": velocity,
        "avg_cycle_time_hours": avg_cycle_hours,
        "overdue_tasks": overdue,
        "member_workload": [
            {"member": m, "active_tasks": c, "story_points": sp} for m, c, sp in member_workload
        ],
    }
