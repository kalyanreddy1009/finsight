-- Single-owner password credential. Browser sessions reuse the devices table (platform WEB_ADMIN).
CREATE TABLE owner_credentials (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    password_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
