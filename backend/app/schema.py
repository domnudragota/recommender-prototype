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

-- recommendation impressions

CREATE TABLE IF NOT EXISTS rec_impressions (
  recset_id     TEXT PRIMARY KEY,              -- UUID string
  user_id       INTEGER NOT NULL,
  platform      TEXT NOT NULL DEFAULT 'web',    -- 'web' | 'mobile'
  ts            INTEGER NOT NULL,               -- unix timestamp
  k             INTEGER NOT NULL,               -- number of items returned
  engine        TEXT NOT NULL,                  -- 'baseline' now, later 'nn'
  item_ids_json TEXT NOT NULL,                  -- JSON array of item_ids in ranked order
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_rec_impressions_user_ts
ON rec_impressions(user_id, ts);

CREATE INDEX IF NOT EXISTS idx_rec_impressions_ts
ON rec_impressions(ts);


-- engagement events (click/like/watch) linked to an impression

CREATE TABLE IF NOT EXISTS engagements (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  recset_id   TEXT NOT NULL,
  user_id     INTEGER NOT NULL,
  item_id     INTEGER NOT NULL,
  action_type TEXT NOT NULL,                    -- 'click' | 'like' | 'watch' etc.
  platform    TEXT NOT NULL DEFAULT 'web',
  ts          INTEGER NOT NULL,                 -- unix timestamp
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (recset_id) REFERENCES rec_impressions(recset_id),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE INDEX IF NOT EXISTS idx_engagements_recset
ON engagements(recset_id);

CREATE INDEX IF NOT EXISTS idx_engagements_user_ts
ON engagements(user_id, ts);
"""
