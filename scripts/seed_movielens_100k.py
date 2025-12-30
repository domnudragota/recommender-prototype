#!/usr/bin/env python3
import argparse
import os
import sqlite3
from backend.app.db import connect, init_db

def load_genres(path: str) -> list[str]:
    id_to_name: dict[int, str] = {}
    max_id = -1

    with open(path, "r", encoding="latin-1") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            name, gid = line.split("|")
            gid = int(gid)
            id_to_name[gid] = name
            if gid > max_id:
                max_id = gid

    # index == genre id (so u.item flags match correctly)
    return [id_to_name[i] for i in range(max_id + 1)]


def seed_users(conn: sqlite3.Connection, u_user_path: str) -> None:
    rows = []
    with open(u_user_path, "r", encoding="latin-1") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) < 5:
                continue
            user_id = int(parts[0])
            age = int(parts[1])
            gender = parts[2]
            occupation = parts[3]
            zip_code = parts[4]
            rows.append((user_id, age, gender, occupation, zip_code))
    conn.executemany(
        "INSERT OR REPLACE INTO users(id, age, gender, occupation, zip_code) VALUES(?,?,?,?,?)",
        rows,
    )

def seed_items(conn: sqlite3.Connection, u_item_path: str, genres_order: list[str]) -> None:
    rows = []
    with open(u_item_path, "r", encoding="latin-1") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) < 5:
                continue

            movie_id = int(parts[0])
            title = parts[1]
            release_date = parts[2] or None
            imdb_url = parts[4] or None

            # genre flags start after imdb_url (index 5)
            flags = parts[5:]
            g = []
            for i, flag in enumerate(flags):
                if i >= len(genres_order):
                    break
                if flag == "1":
                    gname = genres_order[i]
                    if gname.lower() != "unknown":
                        g.append(gname)
            rows.append((movie_id, title, release_date, imdb_url, ",".join(g)))

    conn.executemany(
        "INSERT OR REPLACE INTO items(id, title, release_date, imdb_url, genres) VALUES(?,?,?,?,?)",
        rows,
    )

def seed_interactions(conn: sqlite3.Connection, u_data_path: str, platform: str) -> None:
    rows = []
    with open(u_data_path, "r", encoding="latin-1") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            user_id = int(parts[0])
            item_id = int(parts[1])
            rating = int(parts[2])
            ts = int(parts[3])
            rows.append((user_id, item_id, "rating", rating, float(rating), platform, ts))

    conn.executemany(
        """
        INSERT INTO interactions(user_id, item_id, event_type, rating, weight, platform, ts)
        VALUES(?,?,?,?,?,?,?)
        """,
        rows,
    )

def clear_tables(conn: sqlite3.Connection) -> None:
    # delete child tables first (due to foreign keys)
    conn.execute("DELETE FROM engagements;")
    conn.execute("DELETE FROM rec_impressions;")
    conn.execute("DELETE FROM interactions;")
    conn.execute("DELETE FROM items;")
    conn.execute("DELETE FROM users;")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default="data/movielens/ml-100k")
    ap.add_argument("--platform", default="web", choices=["web", "mobile"])
    ap.add_argument("--reset", action="store_true", help="Clear tables before seeding")
    args = ap.parse_args()

    dataset_dir = args.dataset_dir
    u_user = os.path.join(dataset_dir, "u.user")
    u_item = os.path.join(dataset_dir, "u.item")
    u_genre = os.path.join(dataset_dir, "u.genre")
    u_data = os.path.join(dataset_dir, "u.data")

    for p in [u_user, u_item, u_genre, u_data]:
        if not os.path.exists(p):
            raise SystemExit(f"Missing dataset file: {p}\nRun fetch script first.")

    conn = connect()
    init_db(conn)

    if args.reset:
        clear_tables(conn)

    genres_order = load_genres(u_genre)
    seed_users(conn, u_user)
    seed_items(conn, u_item, genres_order)
    seed_interactions(conn, u_data, args.platform)

    conn.commit()
    conn.close()
    print("Seeding complete.")

if __name__ == "__main__":
    main()
