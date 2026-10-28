import asyncio
import os
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.concurrency import run_in_threadpool

from app.api import (
    admin, analytics, appointments, auth, bookings, notifications, operations, product, queues, services, staff,
    tickets, venues, wayzen,
)
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.logging_config import logger
from app.core.middleware import SecurityMiddleware
from app.core.rate_limit import rate_limit
from app.core.redis_client import redis_client
from app.services import realtime


def _monitor_tick() -> None:
    """One queue-monitor pass. A short Redis lock keeps multiple instances from
    duplicating work; notification dedupe keys make it safe even without Redis."""
    from app.services.booking.queue_ops import run_monitor_once
    try:
        if not redis_client.set("qf:lock:queue-monitor", "1", nx=True,
                                ex=max(5, settings.QUEUE_MONITOR_INTERVAL_SECONDS - 5)):
            return
    except Exception:
        pass
    with SessionLocal() as db:
        run_monitor_once(db)


async def _monitor_loop() -> None:
    while True:
        await asyncio.sleep(settings.QUEUE_MONITOR_INTERVAL_SECONDS)
        try:
            await run_in_threadpool(_monitor_tick)
        except Exception:
            logger.exception("Queue monitor pass failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    realtime.hub.loop = asyncio.get_running_loop()
    tasks = []
    if settings.ENV != "test":
        if settings.REALTIME_BACKEND == "redis":
            tasks.append(asyncio.create_task(realtime.subscriber_loop()))
        tasks.append(asyncio.create_task(_monitor_loop()))
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(
    title="QueueFlow API",
    description="Queues, hospital and shop appointments, hotel reservations and the Wayzen assistant.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
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


@app.exception_handler(IntegrityError)
async def integrity_error(_: Request, exc: IntegrityError):
    logger.warning(f"Integrity error: {exc.orig.__class__.__name__}")
    return JSONResponse(status_code=409, content={"detail": "This conflicts with existing data. Refresh and retry."})


@app.exception_handler(OperationalError)
async def operational_error(_: Request, exc: OperationalError):
    logger.error(f"Database unavailable: {exc.orig.__class__.__name__}")
    return JSONResponse(status_code=503, content={"detail": "The service is temporarily unavailable. Please retry."})


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = [{"loc": [str(p) for p in e.get("loc", ())], "msg": str(e.get("msg", "Invalid value"))
               .removeprefix("Value error, ")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


app.include_router(auth.router)
app.include_router(services.router)
app.include_router(queues.router)
app.include_router(staff.router)
app.include_router(tickets.router)
app.include_router(appointments.router)
app.include_router(analytics.router)
app.include_router(product.router)
app.include_router(venues.router)
app.include_router(bookings.router)
app.include_router(operations.router)
app.include_router(notifications.router)
app.include_router(admin.router)
app.include_router(wayzen.router, dependencies=[Depends(rate_limit)])


@app.get("/api/health")
def health():
    db_ok = redis_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    try:
        redis_client.ping()
    except Exception:
        redis_ok = False
    knowledge_chunks = None
    if db_ok:
        try:
            from app.models.assistant import DocumentChunk
            from app.rag.embeddings import get_embedder
            with SessionLocal() as db:
                knowledge_chunks = db.query(DocumentChunk.id).filter(
                    DocumentChunk.embedding_model == get_embedder().model_id).count()
        except Exception:
            knowledge_chunks = None
    healthy = db_ok and redis_ok
    return JSONResponse(status_code=200 if healthy else 503, content={
        "status": "healthy" if healthy else "degraded",
        "service": settings.APP_NAME,
        "revision": os.environ.get("APP_REVISION") or os.environ.get("RENDER_GIT_COMMIT"),
        "database": "up" if db_ok else "down",
        "redis": "up" if redis_ok else "down",
        "assistant": "full" if settings.llm_configured else "limited",
        # 0 means the knowledge index is empty or was built with another embedding model:
        # run `python -m app.rag.ingest`.
        "knowledge_chunks": knowledge_chunks,
    })


@app.get("/")
def root():
    return {"message": "QueueFlow API — see /docs for API documentation"}
