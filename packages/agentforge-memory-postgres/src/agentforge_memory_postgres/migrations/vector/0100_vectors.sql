CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS vectors (
    id        TEXT PRIMARY KEY,
    embedding vector(${dimensions}) NOT NULL,
    text      TEXT NOT NULL,
    metadata  JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_vectors_embedding
    ON vectors USING hnsw (embedding vector_cosine_ops);
ALTER TABLE vectors
    ADD COLUMN IF NOT EXISTS embedding_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED;
CREATE INDEX IF NOT EXISTS idx_vectors_tsv
    ON vectors USING gin (embedding_tsv);
