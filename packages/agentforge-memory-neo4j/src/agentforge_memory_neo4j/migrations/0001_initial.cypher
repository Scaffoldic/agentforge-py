CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE;
CREATE INDEX claim_project_agent IF NOT EXISTS FOR (c:Claim) ON (c.project, c.agent);
CREATE INDEX claim_run_id IF NOT EXISTS FOR (c:Claim) ON (c.run_id);
CREATE INDEX claim_category IF NOT EXISTS FOR (c:Claim) ON (c.category);
CREATE CONSTRAINT af_node_id IF NOT EXISTS FOR (n:AfNode) REQUIRE n._af_id IS UNIQUE;
CREATE INDEX af_node_labels IF NOT EXISTS FOR (n:AfNode) ON (n._af_labels);
CREATE INDEX af_edge_type IF NOT EXISTS FOR ()-[r:AF_EDGE]-() ON (r._af_edge_type);
