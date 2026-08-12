-- OBJ77 v2: preserve legacy 768-D video data; activate 1152-D media and
-- 256-D projected Brain cosine spaces. Requires sqlite-vec and sha256_blob().

CREATE TABLE video_units_legacy_768_archive (
    id                    INTEGER PRIMARY KEY,
    parent_id             INTEGER,
    level                 TEXT NOT NULL,
    media_id              INTEGER NOT NULL,
    media_hash            TEXT NOT NULL,
    start_time            REAL NOT NULL,
    end_time              REAL NOT NULL,
    motion_score          REAL,
    brightness            REAL,
    saturation            REAL,
    color_temp            REAL,
    metadata_json         TEXT,
    archived_at_utc       TEXT NOT NULL,
    regeneration_required INTEGER NOT NULL CHECK(regeneration_required = 1)
);

INSERT INTO video_units_legacy_768_archive (
    id,parent_id,level,media_id,media_hash,start_time,end_time,motion_score,
    brightness,saturation,color_temp,metadata_json,archived_at_utc,
    regeneration_required
)
SELECT id,parent_id,level,media_id,media_hash,start_time,end_time,motion_score,
       brightness,saturation,color_temp,metadata_json,obj77_utc_now(),1
FROM video_units;

CREATE TABLE video_embeddings_legacy_768_archive (
    rowid                 INTEGER PRIMARY KEY,
    embedding             BLOB NOT NULL,
    embedding_sha256      TEXT NOT NULL CHECK(length(embedding_sha256) = 64),
    archived_at_utc       TEXT NOT NULL,
    regeneration_required INTEGER NOT NULL CHECK(regeneration_required = 1),
    FOREIGN KEY(rowid) REFERENCES video_units_legacy_768_archive(id)
);

INSERT INTO video_embeddings_legacy_768_archive (
    rowid,embedding,embedding_sha256,archived_at_utc,regeneration_required
)
SELECT rowid,embedding,sha256_blob(embedding),obj77_utc_now(),1
FROM video_embeddings;

DELETE FROM video_units;
DROP TABLE video_embeddings;

CREATE VIRTUAL TABLE video_embeddings USING vec0(
    embedding FLOAT[1152]
);

CREATE TABLE brain_units (
    id                  INTEGER PRIMARY KEY,
    project_uuid        TEXT NOT NULL,
    owner_uuid          TEXT NOT NULL,
    media_id            INTEGER NOT NULL,
    media_hash          TEXT NOT NULL,
    recovery_generation TEXT NOT NULL,
    write_receipt_json  TEXT NOT NULL,
    metadata_json       TEXT
);

CREATE INDEX idx_brain_units_project_media
ON brain_units(project_uuid, media_id);

CREATE VIRTUAL TABLE brain_embeddings USING vec0(
    embedding FLOAT[256] distance_metric=cosine
);

CREATE TABLE embedding_store_identity (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id = 1),
    project_uuid TEXT NOT NULL UNIQUE,
    owner_uuid   TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK(schema_version = 2)
);
