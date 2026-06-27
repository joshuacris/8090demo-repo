"""Vault API — main application."""

from fastapi import FastAPI
from .notes import router as notes_router

app = FastAPI(title="Vault API", version="0.1.0")

app.include_router(notes_router)


@app.get("/health")
def health():
    return {"status": "ok"}
