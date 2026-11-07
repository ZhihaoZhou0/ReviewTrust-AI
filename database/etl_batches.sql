
CREATE SCHEMA IF NOT EXISTS reviewtrust;

CREATE TABLE IF NOT EXISTS reviewtrust.etl_batches (
    batch_id CHAR(64) PRIMARY KEY,
    source_revision TEXT NOT NULL,
    batch_number INTEGER NOT NULL,
    input_rows INTEGER NOT NULL,
    inserted_rows INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL
        CHECK (status IN ('completed', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS etl_batches_status_idx
ON reviewtrust.etl_batches (status);
