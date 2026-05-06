-- Hirn-Store: hash-basierter Embedding-Cache (Plan Phase 2/3).

CREATE TABLE IF NOT EXISTS media_embedding_index (
    media_hash      TEXT PRIMARY KEY,
    media_type      TEXT NOT NULL,
    embedding_path  TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    computed_at     TEXT NOT NULL,
    file_size_bytes INTEGER
);

CREATE INDEX IF NOT EXISTS idx_model ON media_embedding_index(model_name, model_version);
