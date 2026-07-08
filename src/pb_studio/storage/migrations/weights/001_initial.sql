-- Hirn-Store: gelernte Achsen-Gewichte (Beta-Bernoulli, Plan Phase 3).

CREATE TABLE IF NOT EXISTS axis_weights (
    axis           TEXT NOT NULL,
    context_level  INTEGER NOT NULL,
    context_key    TEXT NOT NULL,
    positive_count REAL NOT NULL DEFAULT 0,
    negative_count REAL NOT NULL DEFAULT 0,
    last_updated   TEXT NOT NULL,
    PRIMARY KEY (axis, context_level, context_key)
);

CREATE INDEX IF NOT EXISTS idx_axis_level ON axis_weights(axis, context_level);
