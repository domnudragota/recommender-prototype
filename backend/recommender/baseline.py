from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
import math
import sqlite3


@dataclass
class RecItem:
    item_id: int
    title: str
    genres: List[str]
    score: float
    stats: Dict[str, float]


def _parse_genres(genres_csv: str | None) -> List[str]:
    if not genres_csv:
        return []
    parts = [g.strip() for g in genres_csv.split(",")]
    return [g for g in parts if g]


def _get_user_interaction_count(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM interactions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return int(row["c"]) if row else 0


def _get_user_seen_item_ids(conn: sqlite3.Connection, user_id: int) -> set[int]:
    rows = conn.execute(
        "SELECT DISTINCT item_id FROM interactions WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    seen = set()
    for r in rows:
        seen.add(int(r["item_id"]))
    return seen


def _build_user_genre_affinity(conn: sqlite3.Connection, user_id: int) -> Dict[str, float]:
    """
      simple profile:
    - take items the user rated >= 4
    - count genres, weight by (rating - 3) so 4 -> 1, 5 -> 2
    - normalize to 0..1-ish weights
    """
    rows = conn.execute(
        """
        SELECT i.genres, x.rating
        FROM interactions x
        JOIN items i ON i.id = x.item_id
        WHERE x.user_id = ? AND x.rating IS NOT NULL AND x.rating >= 4
        """,
        (user_id,),
    ).fetchall()

    raw: Dict[str, float] = {}
    total = 0.0

    for r in rows:
        rating = int(r["rating"])
        w = float(rating - 3)  # 4->1, 5->2
        genres = _parse_genres(r["genres"])
        for g in genres:
            raw[g] = raw.get(g, 0.0) + w
            total += w

    if total <= 0.0:
        return {}

    # normalize
    for g in list(raw.keys()):
        raw[g] = raw[g] / total

    return raw


def recommend_baseline(
    conn: sqlite3.Connection,
    user_id: int,
    k: int = 10,
    platform: str = "web",
    candidates_limit: int = 2000,
) -> List[RecItem]:
    """
      baseline recommender:
    - candidates = top 'candidates_limit' popular items (by interaction count) excluding seen
    - score = popularity_score + avg_rating_score + genre_match_score

    platform is accepted for API consistency (used later for logging/metrics),
    but not used in scoring yet
    """
    k = max(1, min(int(k), 100))

    seen = _get_user_seen_item_ids(conn, user_id)
    genre_aff = _build_user_genre_affinity(conn, user_id)

    # candidate pool: popular items globally (count + avg rating)
    # join items to get title/genres
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

    scored: List[RecItem] = []

    # precompute maxes for normalization
    max_count = 1.0
    max_avg_rating = 5.0

    for r in cand_rows:
        c = float(r["interaction_count"] or 0.0)
        if c > max_count:
            max_count = c

    for r in cand_rows:
        item_id = int(r["item_id"])
        if item_id in seen:
            continue

        title = str(r["title"])
        genres_list = _parse_genres(r["genres"])
        count = float(r["interaction_count"] or 0.0)
        avg_rating = float(r["avg_rating"] or 0.0)

        # scoring components
        # popularity: log-normalized (so top items don't dominate too hard)
        popularity_score = math.log1p(count) / math.log1p(max_count)

        # avg rating: normalize to 0..1 (MovieLens ratings are 1..5)
        avg_rating_score = max(0.0, min(avg_rating / max_avg_rating, 1.0))

        # genre match: sum user affinity over item's genres (0..1-ish)
        genre_match_score = 0.0
        if genre_aff:
            for g in genres_list:
                genre_match_score += genre_aff.get(g, 0.0)
            # clamp to [0,1]
            genre_match_score = max(0.0, min(genre_match_score, 1.0))

        # weights (tweakable)
        score = (
            0.55 * popularity_score
            + 0.25 * avg_rating_score
            + 0.20 * genre_match_score
        )

        scored.append(
            RecItem(
                item_id=item_id,
                title=title,
                genres=genres_list,
                score=score,
                stats={
                    "interaction_count": count,
                    "avg_rating": avg_rating,
                    "popularity_score": popularity_score,
                    "avg_rating_score": avg_rating_score,
                    "genre_match_score": genre_match_score,
                },
            )
        )

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:k]
