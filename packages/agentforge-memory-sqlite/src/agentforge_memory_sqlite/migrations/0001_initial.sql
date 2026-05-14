CREATE TABLE IF NOT EXISTS claims (
    id          TEXT PRIMARY KEY,
    project     TEXT NOT NULL,
    agent       TEXT NOT NULL,
    run_id      TEXT NOT NULL,
    category    TEXT NOT NULL,
    payload     TEXT NOT NULL,
    supersedes  TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_project_agent
    ON claims(project, agent);
CREATE INDEX IF NOT EXISTS idx_claims_run_id
    ON claims(run_id);
CREATE INDEX IF NOT EXISTS idx_claims_category
    ON claims(category);

CREATE TABLE IF NOT EXISTS vectors (
    id          TEXT PRIMARY KEY,
    vector      BLOB NOT NULL,
    text        TEXT NOT NULL,
    metadata    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vector_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
