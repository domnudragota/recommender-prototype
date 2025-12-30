from contextlib import asynccontextmanager
import json
import time
import uuid
import os

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.logging_setup import setup_logging
from backend.app.db import connect, init_db
from backend.recommender.baseline import recommend_baseline
from backend.recommender.nn_infer import recommend_nn

setup_logging(settings.log_level)

MODEL_PATH_DEFAULT = "models/nn_recommender.pt"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ensure DB exists
    conn = connect()
    init_db(conn)
    conn.close()

    # try to load NN model
    app.state.nn_model = None
    app.state.nn_num_users = None
    app.state.nn_num_items = None

    model_path = os.getenv("NN_MODEL_PATH", MODEL_PATH_DEFAULT)

    try:
        import torch
        from backend.recommender.nn_model import NeuralRecClassifier

        if os.path.exists(model_path):
            artifact = torch.load(model_path, map_location="cpu")
            num_users = int(artifact["num_users"])
            num_items = int(artifact["num_items"])
            embed_dim = int(artifact["embed_dim"])

            model = NeuralRecClassifier(num_users=num_users, num_items=num_items, embed_dim=embed_dim)
            model.load_state_dict(artifact["model_state_dict"])
            model.eval()

            app.state.nn_model = model
            app.state.nn_num_users = num_users
            app.state.nn_num_items = num_items
        # else: no model, baseline still works
    except Exception:
        # any torch/model loading issue -> keep nn disabled (baseline still works)
        app.state.nn_model = None
        app.state.nn_num_users = None
        app.state.nn_num_items = None

    yield
    # nothing to clean up for sqlite here


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/")
def root():
    return {"message": "Recommender prototype API is running", "docs": "/docs", "health": "/health"}


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

@app.get("/debug/model")
def debug_model():
    return {
        "nn_loaded": app.state.nn_model is not None,
        "num_users": app.state.nn_num_users,
        "num_items": app.state.nn_num_items,
        "model_path": os.getenv("NN_MODEL_PATH", MODEL_PATH_DEFAULT),
    }

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


# Recommendations
@app.get("/recommendations")
def recommendations(
    user_id: int = Query(..., ge=1),
    k: int = Query(10, ge=1, le=100),
    platform: str = Query("web"),
    engine: str = Query("auto"),  # "auto" | "baseline" | "nn"
):
    conn = connect()

    # if user does not exist, return 404
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    nn_model = app.state.nn_model
    nn_num_users = app.state.nn_num_users
    nn_num_items = app.state.nn_num_items

    # "auto" policy: use NN only if model is loaded and user has some history
    used_engine = engine
    recs = []

    if engine == "baseline":
        recs = recommend_baseline(conn, user_id=user_id, k=k, platform=platform)
        used_engine = "baseline"

    elif engine == "nn":
        if nn_model is None:
            conn.close()
            raise HTTPException(status_code=400, detail="NN model not loaded. Train it and restart the API.")
        recs = recommend_nn(
            conn,
            model=nn_model,
            num_users=int(nn_num_users),
            num_items=int(nn_num_items),
            user_id=user_id,
            k=k,
        )
        used_engine = "nn"

    elif engine == "auto":
        # require at least N interactions to trust NN
        row = conn.execute("SELECT COUNT(*) AS c FROM interactions WHERE user_id = ?", (user_id,)).fetchone()
        n_interactions = int(row["c"]) if row else 0

        if nn_model is not None and n_interactions >= 5 and user_id <= int(nn_num_users or 0):
            nn_recs = recommend_nn(
                conn,
                model=nn_model,
                num_users=int(nn_num_users),
                num_items=int(nn_num_items),
                user_id=user_id,
                k=k,
            )
            if nn_recs:
                recs = nn_recs
                used_engine = "nn"
            else:
                recs = recommend_baseline(conn, user_id=user_id, k=k, platform=platform)
                used_engine = "baseline"
        else:
            recs = recommend_baseline(conn, user_id=user_id, k=k, platform=platform)
            used_engine = "baseline"

    else:
        conn.close()
        raise HTTPException(status_code=400, detail="engine must be one of: auto, baseline, nn")

    item_ids = [r.item_id for r in recs]

    # log impression (M5/M6 still works, now with engine=baseline/nn)
    recset_id = str(uuid.uuid4())
    ts = int(time.time())
    conn.execute(
        """
        INSERT INTO rec_impressions(recset_id, user_id, platform, ts, k, engine, item_ids_json)
        VALUES(?,?,?,?,?,?,?)
        """,
        (recset_id, user_id, platform, ts, len(item_ids), used_engine, json.dumps(item_ids)),
    )
    conn.commit()
    conn.close()

    return {
        "recset_id": recset_id,
        "user_id": user_id,
        "k": k,
        "platform": platform,
        "engine": used_engine,
        "items": [
            {
                "item_id": r.item_id,
                "title": r.title,
                "genres": r.genres,
                "score": r.score,   # baseline: weighted score; nn: p_like
                "stats": r.stats,
            }
            for r in recs
        ],
    }



# Engagement logging (M5)
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

@app.get("/metrics/pac")
def metrics_pac(
    start_ts: int | None = Query(default=None, ge=0),
    end_ts: int | None = Query(default=None, ge=0),
    k: int = Query(10, ge=1, le=100),
    window_hours: int = Query(24, ge=1, le=168),
    platform: str | None = Query(default=None),
    engine: str | None = Query(default=None),
    action_types: str = Query("click"),
):
    # default: last 7 days
    now = int(time.time())
    if end_ts is None:
        end_ts = now
    if start_ts is None:
        start_ts = end_ts - 7 * 24 * 3600

    if start_ts > end_ts:
        raise HTTPException(status_code=400, detail="start_ts must be <= end_ts")

    window_sec = window_hours * 3600
    allowed_actions = {a.strip() for a in action_types.split(",") if a.strip()}
    if not allowed_actions:
        raise HTTPException(status_code=400, detail="action_types must contain at least one value")

    conn = connect()

    sql = """
        SELECT recset_id, user_id, platform, ts, k, engine, item_ids_json
        FROM rec_impressions
        WHERE ts >= ? AND ts <= ?
    """
    params: list[object] = [start_ts, end_ts]

    if platform is not None:
        sql += " AND platform = ?"
        params.append(platform)

    if engine is not None:
        sql += " AND engine = ?"
        params.append(engine)

    sql += " ORDER BY ts ASC"

    impressions = conn.execute(sql, tuple(params)).fetchall()
    if not impressions:
        conn.close()
        return {
            "pac_mean": 0.0,
            "pac_micro": 0.0,
            "impressions": 0,
            "total_hits": 0,
            "total_recommended": 0,
            "k": k,
            "window_hours": window_hours,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "platform": platform,
            "engine": engine,
            "action_types": sorted(list(allowed_actions)),
        }

    pac_sum = 0.0
    denom_sum = 0
    total_hits = 0

    for imp in impressions:
        recset_id = imp["recset_id"]
        imp_ts = int(imp["ts"])

        try:
            item_ids = json.loads(imp["item_ids_json"])
            if not isinstance(item_ids, list):
                item_ids = []
        except Exception:
            item_ids = []

        topk = [int(x) for x in item_ids[:k]]
        if not topk:
            continue

        window_end = imp_ts + window_sec
        q_marks = ",".join(["?"] * len(allowed_actions))

        eng_rows = conn.execute(
            f"""
            SELECT DISTINCT item_id
            FROM engagements
            WHERE recset_id = ?
              AND ts >= ?
              AND ts <= ?
              AND action_type IN ({q_marks})
            """,
            (recset_id, imp_ts, window_end, *allowed_actions),
        ).fetchall()

        engaged_items = {int(r["item_id"]) for r in eng_rows}
        hits = sum(1 for item_id in topk if item_id in engaged_items)

        pac_sum += hits / len(topk)
        denom_sum += len(topk)
        total_hits += hits

    conn.close()

    pac_mean = pac_sum / len(impressions) if impressions else 0.0
    pac_micro = total_hits / denom_sum if denom_sum else 0.0

    return {
        "pac_mean": pac_mean,
        "pac_micro": pac_micro,
        "impressions": len(impressions),
        "total_hits": total_hits,
        "total_recommended": denom_sum,
        "k": k,
        "window_hours": window_hours,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "platform": platform,
        "engine": engine,
        "action_types": sorted(list(allowed_actions)),
    }
