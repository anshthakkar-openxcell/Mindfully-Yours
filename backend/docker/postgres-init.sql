-- Runs once, automatically, the first time the postgres container's data volume is created.
-- pgvector's `vector` column type (used by every embedding column in app/db/models/) does not
-- exist until this extension is enabled -- without it, table creation/migrations fail.
CREATE EXTENSION IF NOT EXISTS vector;
