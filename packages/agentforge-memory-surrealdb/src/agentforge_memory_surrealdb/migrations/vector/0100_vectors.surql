DEFINE TABLE IF NOT EXISTS af_vector SCHEMALESS;
DEFINE INDEX IF NOT EXISTS af_vector_id_idx
    ON af_vector FIELDS af_id UNIQUE;
DEFINE INDEX IF NOT EXISTS af_vector_hnsw_idx
    ON af_vector FIELDS embedding HNSW DIMENSION ${dimensions} DIST COSINE;
