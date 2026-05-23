-- Migration 002: Sicheres Härten des Primary Keys für embedding_cache.db, falls ältere DBs noch einen Single-Key nutzen.

CREATE TABLE IF NOT EXISTS media_embedding_index_new (
    media_hash      TEXT NOT NULL,
    media_type      TEXT NOT NULL,
    embedding_path  TEXT NOT NULL,
    model_name      TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    computed_at     TEXT NOT NULL,
    file_size_bytes INTEGER,
    PRIMARY KEY (media_hash, model_name, model_version)
);

-- Falls die alte Tabelle existiert, Daten kopieren
INSERT OR IGNORE INTO media_embedding_index_new 
SELECT media_hash, media_type, embedding_path, model_name, model_version, computed_at, file_size_bytes 
FROM media_embedding_index;

DROP TABLE media_embedding_index;

ALTER TABLE media_embedding_index_new RENAME TO media_embedding_index;

CREATE INDEX IF NOT EXISTS idx_model ON media_embedding_index(model_name, model_version);

PRAGMA user_version = 2;
