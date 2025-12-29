from contextlib import asynccontextmanager

from fastapi import FastAPI, Query

from backend.app.config import settings
from backend.app.logging_setup import setup_logging
from backend.app.db import connect, init_db

setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # check DB file + tables exist even before seeding
    conn = connect()
    init_db(conn)
    conn.close()

    yield

    # nothing to clean up for sqlite here


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }


@app.get("/")
def root():
    return {
        "message": "Recommender prototype API is running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/debug/users")
def debug_users(limit: int = Query(10, ge=1, le=200)):
    conn = connect()
    rows = conn.execute(
        "SELECT id, age, gender, occupation, zip_code FROM users ORDER BY id LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/debug/items")
def debug_items(limit: int = Query(10, ge=1, le=200)):
    conn = connect()
    rows = conn.execute(
        "SELECT id, title, release_date, genres FROM items ORDER BY id LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/debug/interactions")
def debug_interactions(
    user_id: int = Query(..., ge=1),
    limit: int = Query(20, ge=1, le=200),
):
    conn = connect()
    rows = conn.execute(
        """
        SELECT user_id, item_id, event_type, rating, weight, platform, ts
        FROM interactions
        WHERE user_id = ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
