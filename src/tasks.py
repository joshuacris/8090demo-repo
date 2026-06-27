"""Task CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from .models import Task, TaskStatus, Sprint
from .cache import invalidate_team
from .database import get_db

router = APIRouter()


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: str = "medium"
    assignee_id: Optional[int] = None
    sprint_id: int
    story_points: int = 1


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[str] = None
    assignee_id: Optional[int] = None
    story_points: Optional[int] = None


@router.post("/api/tasks")
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = Task(**payload.dict())
    db.add(task)
    db.commit()
    db.refresh(task)
    # New task affects workload and status_breakdown
    invalidate_team(task.sprint.team_id, ["status_breakdown", "workload"])
    return task


@router.put("/api/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    # Invalidate dashboard cache — status_breakdown and workload change on any task mutation
    # Velocity only changes on status->DONE, but invalidate it too for simplicity
    invalidate_team(task.sprint.team_id, ["status_breakdown", "workload", "velocity"])
    return task


@router.get("/api/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
