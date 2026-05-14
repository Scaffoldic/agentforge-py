CREATE TABLE IF NOT EXISTS claims (
    id         TEXT PRIMARY KEY,
    project    TEXT NOT NULL,
    agent      TEXT NOT NULL,
    run_id     TEXT NOT NULL,
    category   TEXT NOT NULL,
    payload    JSONB NOT NULL,
    supersedes TEXT,
    created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_claims_project_agent ON claims(project, agent);
CREATE INDEX IF NOT EXISTS idx_claims_run_id ON claims(run_id);
CREATE INDEX IF NOT EXISTS idx_claims_category ON claims(category);
