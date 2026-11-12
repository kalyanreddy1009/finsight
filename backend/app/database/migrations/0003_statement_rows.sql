-- Staged statement rows awaiting review / commit to the ledger.
CREATE TABLE statement_rows (
    id TEXT PRIMARY KEY,
    statement_id TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    tx_date DATE NOT NULL,
    raw_description TEXT NOT NULL,
    clean_description TEXT NOT NULL,
    channel TEXT NOT NULL,
    extracted_vpa TEXT,
    external_reference TEXT,
    dedup_fingerprint TEXT NOT NULL,
    amount_minor INTEGER NOT NULL CHECK (typeof(amount_minor) = 'integer' AND amount_minor > 0),
    direction TEXT NOT NULL CHECK (direction IN ('DEBIT', 'CREDIT')),
    stated_balance_minor INTEGER,
    balance_verified INTEGER NOT NULL DEFAULT 0 CHECK (balance_verified IN (0, 1)),
    merchant_id TEXT REFERENCES merchants(id),
    suggested_category_id TEXT REFERENCES categories(id),
    confidence_score REAL NOT NULL DEFAULT 0.0,
    row_status TEXT NOT NULL CHECK (row_status IN (
        'PENDING_REVIEW', 'AUTO_APPROVED', 'USER_APPROVED', 'REJECTED', 'DUPLICATE', 'COMMITTED'
    )),
    duplicate_of_transaction_id TEXT REFERENCES transactions(id),
    provisional_match_transaction_id TEXT REFERENCES transactions(id),
    committed_transaction_id TEXT REFERENCES transactions(id),
    duplicate_override INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_override IN (0, 1)),
    UNIQUE (statement_id, row_index)
);

CREATE INDEX idx_statement_rows_status ON statement_rows(statement_id, row_status);
