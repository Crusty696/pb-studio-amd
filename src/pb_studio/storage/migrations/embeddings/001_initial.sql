-- Project-store embeddings.db — audio (3-tier) + video (2-tier).
-- Plan Phase 2/4 (Projekt-Store).

CREATE TABLE IF NOT EXISTS audio_units (
    id            INTEGER PRIMARY KEY,
    parent_id     INTEGER,
    level         TEXT NOT NULL,
    media_id      INTEGER NOT NULL,
    media_hash    TEXT NOT NULL,
    start_time    REAL NOT NULL,
    end_time      REAL NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY (parent_id) REFERENCES audio_units(id)
);
CREATE INDEX IF NOT EXISTS idx_audio_media ON audio_units(media_id, level);
CREATE INDEX IF NOT EXISTS idx_audio_hash  ON audio_units(media_hash);

CREATE VIRTUAL TABLE IF NOT EXISTS audio_embeddings USING vec0(
    embedding FLOAT[512]
);

CREATE TABLE IF NOT EXISTS video_units (
    id            INTEGER PRIMARY KEY,
    parent_id     INTEGER,
    level         TEXT NOT NULL,
    media_id      INTEGER NOT NULL,
    media_hash    TEXT NOT NULL,
    start_time    REAL NOT NULL,
    end_time      REAL NOT NULL,
    motion_score  REAL,
    brightness    REAL,
    saturation    REAL,
    color_temp    REAL,
    metadata_json TEXT,
    FOREIGN KEY (parent_id) REFERENCES video_units(id)
);
CREATE INDEX IF NOT EXISTS idx_video_media ON video_units(media_id, level);
CREATE INDEX IF NOT EXISTS idx_video_hash  ON video_units(media_hash);

CREATE VIRTUAL TABLE IF NOT EXISTS video_embeddings USING vec0(
    embedding FLOAT[768]
);
