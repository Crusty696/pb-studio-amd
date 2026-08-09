-- Stable project/event identities for exactly-once Projector V2 training.

CREATE TABLE IF NOT EXISTS project_identity (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    project_uuid TEXT NOT NULL UNIQUE
);

ALTER TABLE feedback_events ADD COLUMN project_uuid TEXT;
ALTER TABLE feedback_events ADD COLUMN event_uuid TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_event_uuid
ON feedback_events(event_uuid)
WHERE event_uuid IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_feedback_project_event
ON feedback_events(project_uuid, event_uuid);
