-- Brain weight semantics v2.
-- Preserve the non-replayable v1 Cartesian-product weights in-place and start
-- the sparse evidence-weighted store neutral.

DROP INDEX IF EXISTS idx_axis_level;

ALTER TABLE axis_weights RENAME TO axis_weights_v1_archive;

CREATE TABLE axis_weights (
    axis           TEXT NOT NULL,
    context_level  INTEGER NOT NULL,
    context_key    TEXT NOT NULL,
    positive_count REAL NOT NULL DEFAULT 0,
    negative_count REAL NOT NULL DEFAULT 0,
    last_updated   TEXT NOT NULL,
    PRIMARY KEY (axis, context_level, context_key)
);

CREATE INDEX idx_axis_level ON axis_weights(axis, context_level);

CREATE TABLE brain_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT INTO brain_meta(key, value) VALUES
    ('weight_semantics_version', '2'),
    ('feedback_count', '0'),
    ('legacy_archive_table', 'axis_weights_v1_archive'),
    ('migration_reason', 'v1 event log incomplete; neutral sparse-credit restart');
