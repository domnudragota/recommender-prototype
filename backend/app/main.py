from contextlib import asynccontextmanager
import json
import time
import uuid

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.logging_setup import setup_logging
from backend.app.db import connect, init_db
from backend.recommender.baseline import recommend_baseline

setup_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ensure DB file + tables exist
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


# Debug endpoints
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

# recommendations + impression logging
@app.get("/recommendations")
def recommendations(
    user_id: int = Query(..., ge=1),
    k: int = Query(10, ge=1, le=100),
    platform: str = Query("web"),
    engine: str = Query("baseline"),  # later: "auto" | "nn" | "baseline"
):
    conn = connect()

    # if user does not exist, return 404
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    # for now only baseline is implemented
    if engine != "baseline":
        conn.close()
        raise HTTPException(status_code=400, detail="Only engine=baseline is supported for now")

    # generate recommendations
    recs = recommend_baseline(conn, user_id=user_id, k=k, platform=platform)
    item_ids = [r.item_id for r in recs]

    # log the impression (needed for PaC later)
    recset_id = str(uuid.uuid4())
    ts = int(time.time())
    conn.execute(
        """
        INSERT INTO rec_impressions(recset_id, user_id, platform, ts, k, engine, item_ids_json)
        VALUES(?,?,?,?,?,?,?)
        """,
        (recset_id, user_id, platform, ts, len(item_ids), engine, json.dumps(item_ids)),
    )
    conn.commit()
    conn.close()

    return {
        "recset_id": recset_id,
        "user_id": user_id,
        "k": k,
        "platform": platform,
        "engine": engine,
        "items": [
            {
                "item_id": r.item_id,
                "title": r.title,
                "genres": r.genres,
                "score": r.score,
                "stats": r.stats,  # useful for demo/debug
            }
            for r in recs
        ],
    }

# engagement logging
class EngagementEvent(BaseModel):
    recset_id: str = Field(..., min_length=8)
    user_id: int = Field(..., ge=1)
    item_id: int = Field(..., ge=1)
    action_type: str = Field(..., min_length=1, max_length=32)  # click/like/watch
    platform: str = Field("web", min_length=1, max_length=16)
    ts: int | None = Field(default=None, ge=0)

@app.post("/events/engagement")
def log_engagement(ev: EngagementEvent):
    conn = connect()

    # ensure the impression exists and belongs to the same user
    imp = conn.execute(
        "SELECT recset_id, user_id FROM rec_impressions WHERE recset_id = ?",
        (ev.recset_id,),
    ).fetchone()

    if not imp:
        conn.close()
        raise HTTPException(status_code=404, detail="recset_id not found (no impression logged)")

    if int(imp["user_id"]) != ev.user_id:
        conn.close()
        raise HTTPException(status_code=400, detail="user_id does not match the impression owner")

    ts = ev.ts if ev.ts is not None else int(time.time())

    conn.execute(
        """
        INSERT INTO engagements(recset_id, user_id, item_id, action_type, platform, ts)
        VALUES(?,?,?,?,?,?)
        """,
        (ev.recset_id, ev.user_id, ev.item_id, ev.action_type, ev.platform, ts),
    )
    conn.commit()
    conn.close()

    return {"status": "ok"}


# optional debug endpoints
@app.get("/debug/impressions")
def debug_impressions(
    user_id: int = Query(..., ge=1),
    limit: int = Query(10, ge=1, le=200),
):
    conn = connect()
    rows = conn.execute(
        """
        SELECT recset_id, user_id, platform, ts, k, engine, item_ids_json
        FROM rec_impressions
        WHERE user_id = ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/debug/engagements")
def debug_engagements(
    recset_id: str = Query(..., min_length=8),
    limit: int = Query(50, ge=1, le=200),
):
    conn = connect()
    rows = conn.execute(
        """
        SELECT id, recset_id, user_id, item_id, action_type, platform, ts
        FROM engagements
        WHERE recset_id = ?
        ORDER BY ts DESC
        LIMIT ?
        """,
        (recset_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
