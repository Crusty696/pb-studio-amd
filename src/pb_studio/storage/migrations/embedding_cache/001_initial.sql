-- Hirn-Store: hash-basierter Embedding-Cache (Plan Phase 2/3).

CREATE TABLE IF NOT EXISTS media_embedding_index (
    media_hash      TEXT NOT NULL,
    media_type      TEXT NOT NULL,
    embedding_path  TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    computed_at     TEXT NOT NULL,
    file_size_bytes INTEGER,
    PRIMARY KEY (media_hash, model_name, model_version)
);

CREATE INDEX IF NOT EXISTS idx_model ON media_embedding_index(model_name, model_version);
