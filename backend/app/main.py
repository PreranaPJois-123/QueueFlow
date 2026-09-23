import time

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.logging_config import logger
from app.core.rate_limit import rate_limit
from app.core.database import engine
from app.core.redis_client import redis_client
from app.api import auth, services, queues, staff, tickets, appointments, analytics

app = FastAPI(
    title="QueueFlow API",
    description="Real-time queue & appointment management platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(f"Unhandled error on {request.method} {request.url.path}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)")
    return response


# Global lightweight rate limiting on write-heavy / abuse-prone routes.
app.include_router(auth.router, dependencies=[Depends(rate_limit)])
app.include_router(services.router)
app.include_router(queues.router)
app.include_router(staff.router)
app.include_router(tickets.router)
app.include_router(appointments.router)
app.include_router(analytics.router)


@app.get("/api/health")
def health():
    db_ok = True
    redis_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    try:
        redis_client.ping()
    except Exception:
        redis_ok = False

    status_str = "healthy" if (db_ok and redis_ok) else "degraded"
    return JSONResponse(status_code=200 if db_ok and redis_ok else 503, content={
        "status": status_str,
        "service": settings.APP_NAME,
        "database": "up" if db_ok else "down",
        "redis": "up" if redis_ok else "down",
    })


@app.get("/")
def root():
    return {"message": "QueueFlow API — see /docs for API documentation"}
