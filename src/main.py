"""TeamPulse API — main application."""

from fastapi import FastAPI
from .dashboard import router as dashboard_router
from .tasks import router as tasks_router
from .cache import health_check as redis_health

app = FastAPI(title="TeamPulse", version="1.0.0")

app.include_router(dashboard_router)
app.include_router(tasks_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/redis")
def health_redis():
    """Redis status — separate from main health so Redis being down doesn't make the pod unready."""
    up = redis_health()
    return {"redis": "ok" if up else "down"}
