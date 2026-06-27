"""Task CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from .models import Task, TaskStatus, Sprint
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
    # Denormalized team_id — must be set from sprint
    sprint = db.query(Sprint).filter(Sprint.id == payload.sprint_id).first()
    task.team_id = sprint.team_id
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.put("/api/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    return task


@router.get("/api/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
