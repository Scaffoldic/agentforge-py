DEFINE ANALYZER IF NOT EXISTS af_vector_en
    TOKENIZERS class FILTERS lowercase, ascii;
DEFINE INDEX IF NOT EXISTS af_vector_fts
    ON af_vector FIELDS text SEARCH ANALYZER af_vector_en BM25;
