CREATE CONSTRAINT af_vector_id IF NOT EXISTS FOR (n:AfVector) REQUIRE n.af_id IS UNIQUE;
CREATE VECTOR INDEX af_vector_embedding IF NOT EXISTS FOR (n:AfVector) ON (n.embedding) OPTIONS {indexConfig: { `vector.dimensions`: ${dimensions}, `vector.similarity_function`: 'cosine' }};
CREATE FULLTEXT INDEX af_vector_text IF NOT EXISTS FOR (n:AfVector) ON EACH [n.text];
