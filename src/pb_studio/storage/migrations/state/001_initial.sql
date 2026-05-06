-- Timeline + cuts + raw feedback events (Plan Phase 4 + 5).

CREATE TABLE IF NOT EXISTS timelines (
    id            INTEGER PRIMARY KEY,
    name          TEXT,
    audio_clip_id INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    config_json   TEXT,
    is_current    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS timeline_cuts (
    id                INTEGER PRIMARY KEY,
    timeline_id       INTEGER NOT NULL,
    position_idx      INTEGER NOT NULL,
    clip_id           TEXT NOT NULL,
    start_time        REAL NOT NULL,
    end_time          REAL NOT NULL,
    clip_start        REAL DEFAULT 0,
    trigger_type      TEXT,
    trigger_strength  REAL,
    segment_type      TEXT,
    brain_scores_json TEXT,
    metadata_json     TEXT,
    FOREIGN KEY (timeline_id) REFERENCES timelines(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS feedback_events (
    id                INTEGER PRIMARY KEY,
    cut_id            INTEGER NOT NULL,
    rating            TEXT NOT NULL,
    alpha_delta       REAL NOT NULL,
    beta_delta        REAL NOT NULL,
    context_keys_json TEXT NOT NULL,
    timestamp         TEXT NOT NULL,
    FOREIGN KEY (cut_id) REFERENCES timeline_cuts(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback_events(timestamp);
