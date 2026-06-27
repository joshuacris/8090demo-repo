"""TeamPulse API — main application."""

from fastapi import FastAPI
from .dashboard import router as dashboard_router
from .tasks import router as tasks_router

app = FastAPI(title="TeamPulse", version="1.0.0")

app.include_router(dashboard_router)
app.include_router(tasks_router)


@app.get("/health")
def health():
    return {"status": "ok"}
