DEFINE TABLE IF NOT EXISTS agentforge_migrations SCHEMALESS;
DEFINE INDEX IF NOT EXISTS agentforge_migrations_id_idx
    ON agentforge_migrations FIELDS af_id UNIQUE;
