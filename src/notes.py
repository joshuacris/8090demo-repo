"""Note CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from .models import Note
from .database import get_db

router = APIRouter()


class NoteCreate(BaseModel):
    title: str
    body: str


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None


@router.post("/api/notes")
def create_note(payload: NoteCreate, db: Session = Depends(get_db)):
    note = Note(**payload.dict())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("/api/notes")
def list_notes(db: Session = Depends(get_db)):
    return db.query(Note).order_by(Note.created_at.desc()).all()


@router.get("/api/notes/{note_id}")
def get_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.put("/api/notes/{note_id}")
def update_note(note_id: int, payload: NoteUpdate, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(note, field, value)
    db.commit()
    return note


@router.delete("/api/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
    return {"deleted": note_id}
