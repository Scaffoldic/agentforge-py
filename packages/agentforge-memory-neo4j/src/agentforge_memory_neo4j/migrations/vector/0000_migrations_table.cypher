CREATE CONSTRAINT agentforge_migration_id IF NOT EXISTS
FOR (m:AgentforgeMigration) REQUIRE m.id IS UNIQUE
