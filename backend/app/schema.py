SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id         INTEGER PRIMARY KEY,
  age        INTEGER,
  gender     TEXT,
  occupation TEXT,
  zip_code   TEXT,
  consent    INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
  id           INTEGER PRIMARY KEY,
  title        TEXT NOT NULL,
  release_date TEXT,
  imdb_url     TEXT,
  genres       TEXT, 
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS interactions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL,
  item_id    INTEGER NOT NULL,
  event_type TEXT NOT NULL,  -- "rating" for MovieLens
  rating     INTEGER,        -- 1..5
  weight     REAL,           -- usually same as rating in this dataset
  platform   TEXT NOT NULL DEFAULT 'web',
  ts         INTEGER,        -- unix timestamp from dataset
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE INDEX IF NOT EXISTS idx_interactions_user_id ON interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_item_id ON interactions(item_id);
CREATE INDEX IF NOT EXISTS idx_interactions_ts ON interactions(ts);
"""
