from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import sqlite3

from backend.recommender.baseline import RecItem


def _parse_genres(genres_csv: str | None) -> List[str]:
    if not genres_csv:
        return []
    return [g.strip() for g in genres_csv.split(",") if g.strip()]


def _get_seen_item_ids(conn: sqlite3.Connection, user_id: int) -> set[int]:
    rows = conn.execute(
        "SELECT DISTINCT item_id FROM interactions WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {int(r["item_id"]) for r in rows}


def recommend_nn(
    conn: sqlite3.Connection,
    model: Any,            # torch.nn.Module
    num_users: int,
    num_items: int,
    user_id: int,
    k: int = 10,
    candidates_limit: int = 2000,
) -> List[RecItem]:
    """
    NN-based recommender:
      - build candidate pool from globally popular items (fast)
      - filter out seen items
      - score (user,item) with NN -> probability
      - return top-K unseen items
    """
    # lazy import so the backend can still run without torch for baseline-only usage
    import torch

    user_idx = user_id - 1
    if user_idx < 0 or user_idx >= num_users:
        return []

    seen = _get_seen_item_ids(conn, user_id)

    # popular items (same idea as baseline, but scoring differs)
    cand_rows = conn.execute(
        """
        SELECT
          i.id AS item_id,
          i.title AS title,
          i.genres AS genres,
          COUNT(x.id) AS interaction_count,
          AVG(CASE WHEN x.rating IS NOT NULL THEN x.rating END) AS avg_rating
        FROM items i
        LEFT JOIN interactions x ON x.item_id = i.id
        GROUP BY i.id
        ORDER BY interaction_count DESC
        LIMIT ?
        """,
        (candidates_limit,),
    ).fetchall()

    # filter + map to indices the model understands
    candidates: List[Tuple[int, int, str, str, float, float]] = []
    for r in cand_rows:
        item_id = int(r["item_id"])
        if item_id in seen:
            continue

        item_idx = item_id - 1
        if item_idx < 0 or item_idx >= num_items:
            continue

        title = str(r["title"])
        genres_csv = r["genres"]
        interaction_count = float(r["interaction_count"] or 0.0)
        avg_rating = float(r["avg_rating"] or 0.0)

        candidates.append((item_id, item_idx, title, genres_csv, interaction_count, avg_rating))

    if not candidates:
        return []

    # batch inference
    item_indices = torch.tensor([c[1] for c in candidates], dtype=torch.long)
    user_indices = torch.full_like(item_indices, fill_value=user_idx)

    model.eval()
    with torch.no_grad():
        logits = model(user_indices, item_indices)
        probs = torch.sigmoid(logits).cpu().tolist()

    recs: List[RecItem] = []
    for (item_id, _item_idx, title, genres_csv, interaction_count, avg_rating), p_like in zip(candidates, probs):
        recs.append(
            RecItem(
                item_id=item_id,
                title=title,
                genres=_parse_genres(genres_csv),
                score=float(p_like),  # probability of "like"
                stats={
                    "p_like": float(p_like),
                    "interaction_count": interaction_count,
                    "avg_rating": avg_rating,
                },
            )
        )

    recs.sort(key=lambda x: x.score, reverse=True)
    return recs[:k]
