-- ============================================================================
-- 1. AUTHENTICATION, DEVICES & AUDIT SECURITY
-- ============================================================================
CREATE TABLE devices (
    id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    platform TEXT NOT NULL CHECK (platform IN ('IOS', 'ANDROID', 'WEB_ADMIN')),
    public_key_pem TEXT NOT NULL,
    refresh_token_hash TEXT NOT NULL,
    last_sync_seq INTEGER NOT NULL DEFAULT 0,
    is_revoked INTEGER NOT NULL DEFAULT 0 CHECK (is_revoked IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL CHECK (event_type IN (
        'DEVICE_LOGIN', 'DEVICE_REVOKED', 'STATEMENT_UPLOADED', 'STATEMENT_COMMITTED',
        'AI_CLOUD_CONSENT_GRANTED', 'BACKUP_CREATED', 'BACKUP_RESTORED', 'PASSWORD_VAULT_UPDATED'
    )),
    actor_device_id TEXT REFERENCES devices(id),
    target_object_type TEXT NOT NULL,
    target_object_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ============================================================================
-- 2. ACCOUNTS, CATEGORIES & MERCHANTS
-- ============================================================================
CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    account_class TEXT NOT NULL CHECK (account_class IN ('ASSET', 'LIABILITY', 'EQUITY', 'INCOME', 'EXPENSE')),
    account_subtype TEXT NOT NULL CHECK (account_subtype IN (
        'BANK_SAVINGS', 'BANK_CURRENT', 'CREDIT_CARD', 'CASH', 'WALLET',
        'REIMBURSEMENT_CLEARING', 'INVESTMENT_DEMAT', 'INVESTMENT_MF',
        'FIXED_DEPOSIT', 'PF_EPF_PPF', 'PHYSICAL_ASSET', 'LOAN_HOME',
        'LOAN_VEHICLE', 'LOAN_PERSONAL', 'SYSTEM_CATEGORY', 'OPENING_EQUITY'
    )),
    institution TEXT,
    account_number_masked TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    opening_balance_minor INTEGER NOT NULL DEFAULT 0,
    current_balance_minor INTEGER NOT NULL DEFAULT 0,
    credit_limit_minor INTEGER,
    billing_day INTEGER CHECK (billing_day BETWEEN 1 AND 31),
    due_day INTEGER CHECK (due_day BETWEEN 1 AND 31),
    encrypted_pdf_password TEXT,
    is_liquid INTEGER NOT NULL DEFAULT 1 CHECK (is_liquid IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE account_balance_snapshots (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    snapshot_date DATE NOT NULL,
    balance_minor INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('STATEMENT_RECONCILED', 'CAS_IMPORT', 'MANUAL_VALUATION', 'DAILY_ROLLUP')),
    UNIQUE(account_id, snapshot_date)
);

CREATE TABLE categories (
    id TEXT PRIMARY KEY,
    ledger_account_id TEXT NOT NULL UNIQUE REFERENCES accounts(id),
    name TEXT NOT NULL,
    parent_category_id TEXT REFERENCES categories(id),
    category_type TEXT NOT NULL CHECK (category_type IN ('EXPENSE', 'INCOME', 'TRANSFER', 'INVESTMENT')),
    default_tax_section TEXT NOT NULL DEFAULT 'NONE' CHECK (
        default_tax_section IN ('NONE', '80C', '80D', '80CCD', 'HRA', '24B', 'LTCG', 'STCG')
    ),
    is_discretionary INTEGER NOT NULL DEFAULT 1 CHECK (is_discretionary IN (0, 1)),
    is_sensitive_private INTEGER NOT NULL DEFAULT 0 CHECK (is_sensitive_private IN (0, 1)),
    is_system_category INTEGER NOT NULL DEFAULT 0 CHECK (is_system_category IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE merchants (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    upi_vpa_patterns TEXT NOT NULL DEFAULT '[]', -- JSON array of exact VPA strings
    aliases_json TEXT NOT NULL DEFAULT '[]',     -- JSON array of substring/regex patterns
    embedding_blob BLOB,                         -- 384-dim float32 vector from all-MiniLM-L6-v2
    default_category_id TEXT REFERENCES categories(id),
    is_subscription_merchant INTEGER NOT NULL DEFAULT 0 CHECK (is_subscription_merchant IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ============================================================================
-- 3. STATEMENT INGESTION & PROVENANCE
-- ============================================================================
CREATE TABLE statements (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    statement_kind TEXT NOT NULL CHECK (statement_kind IN ('BANK_PDF', 'CARD_PDF', 'CSV', 'CAS_PDF')),
    original_filename TEXT NOT NULL,
    file_hash_sha256 TEXT NOT NULL UNIQUE,
    layout_fingerprint TEXT NOT NULL,
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    statement_start_date DATE NOT NULL,
    statement_end_date DATE NOT NULL,
    opening_balance_minor INTEGER NOT NULL,
    closing_balance_minor INTEGER NOT NULL,
    computed_closing_minor INTEGER,
    reconciliation_diff_minor INTEGER,
    processing_status TEXT NOT NULL CHECK (
        processing_status IN ('UPLOADED', 'PARSING', 'REVIEW_REQUIRED', 'APPROVED', 'FAILED')
    ),
    uploaded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    approved_at TEXT
);

CREATE TABLE import_errors (
    id TEXT PRIMARY KEY,
    statement_id TEXT NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
    page_number INTEGER,
    row_index INTEGER,
    raw_row_text TEXT,
    error_code TEXT NOT NULL,
    error_message TEXT NOT NULL,
    expected_running_balance_minor INTEGER,
    actual_running_balance_minor INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ============================================================================
-- 4. DOUBLE-ENTRY JOURNAL & OPERATIONAL TRANSACTIONS
-- ============================================================================
CREATE TABLE journal_entries (
    id TEXT PRIMARY KEY,
    entry_date DATE NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN (
        'STANDARD', 'INTERNAL_TRANSFER', 'CARD_SETTLEMENT', 'REFUND',
        'SPLIT_EXPENSE', 'REIMBURSEMENT_SETTLEMENT', 'REVERSAL', 'OPENING_BALANCE'
    )),
    source_statement_id TEXT REFERENCES statements(id),
    reverses_journal_entry_id TEXT REFERENCES journal_entries(id),
    is_provisional INTEGER NOT NULL DEFAULT 0 CHECK (is_provisional IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'POSTED')),
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE journal_lines (
    id TEXT PRIMARY KEY,
    journal_entry_id TEXT NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    signed_amount_minor INTEGER NOT NULL CHECK (signed_amount_minor != 0), -- Positive = DEBIT, Negative = CREDIT
    currency TEXT NOT NULL DEFAULT 'INR',
    memo TEXT
);

CREATE INDEX idx_journal_lines_entry ON journal_lines(journal_entry_id);
CREATE INDEX idx_journal_lines_account ON journal_lines(account_id);

CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    journal_entry_id TEXT NOT NULL UNIQUE REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    counterparty_account_id TEXT NOT NULL REFERENCES accounts(id),
    statement_id TEXT REFERENCES statements(id),
    merchant_id TEXT REFERENCES merchants(id),
    category_id TEXT REFERENCES categories(id),
    transaction_date DATE NOT NULL,
    description TEXT NOT NULL,
    clean_description TEXT NOT NULL,
    extracted_vpa TEXT,
    external_reference TEXT, -- 12-digit UPI UTR / IMPS RRN / NEFT ref
    dedup_fingerprint TEXT NOT NULL,
    amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
    user_share_minor INTEGER NOT NULL CHECK (user_share_minor >= 0),
    direction TEXT NOT NULL CHECK (direction IN ('DEBIT', 'CREDIT')),
    transaction_type TEXT NOT NULL CHECK (transaction_type IN (
        'EXPENSE', 'INCOME', 'TRANSFER', 'CARD_SETTLEMENT', 'REFUND', 'FEE_INTEREST', 'INVESTMENT'
    )),
    linked_transaction_id TEXT REFERENCES transactions(id),
    tax_section TEXT NOT NULL DEFAULT 'NONE',
    is_verified INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0, 1)),
    review_status TEXT NOT NULL CHECK (
        review_status IN ('PROVISIONAL', 'PENDING_REVIEW', 'AUTO_APPROVED', 'USER_APPROVED', 'SUPERSEDED')
    ),
    confidence_score REAL NOT NULL DEFAULT 1.0,
    notes TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_tx_account_date ON transactions(account_id, transaction_date DESC);
CREATE INDEX idx_tx_category_date ON transactions(category_id, transaction_date DESC);
CREATE INDEX idx_tx_external_ref ON transactions(external_reference) WHERE external_reference IS NOT NULL;
CREATE INDEX idx_tx_dedup ON transactions(dedup_fingerprint);

CREATE TABLE reimbursable_splits (
    id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    counterparty_name TEXT NOT NULL,
    counterparty_vpa TEXT,
    owed_amount_minor INTEGER NOT NULL CHECK (owed_amount_minor > 0),
    settled_amount_minor INTEGER NOT NULL DEFAULT 0 CHECK (settled_amount_minor >= 0),
    settlement_transaction_id TEXT REFERENCES transactions(id),
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'PARTIAL', 'SETTLED', 'WRITTEN_OFF')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ============================================================================
-- 5. BUDGETS, RECURRING OBLIGATIONS, INVESTMENTS & GOALS
-- ============================================================================
CREATE TABLE budgets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    period_month TEXT NOT NULL UNIQUE, -- YYYY-MM
    total_limit_minor INTEGER NOT NULL CHECK (total_limit_minor > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE budget_categories (
    id TEXT PRIMARY KEY,
    budget_id TEXT NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    category_id TEXT NOT NULL REFERENCES categories(id),
    limit_minor INTEGER NOT NULL CHECK (limit_minor > 0),
    alert_threshold_pct INTEGER NOT NULL DEFAULT 80,
    UNIQUE(budget_id, category_id)
);

CREATE TABLE recurring_rules (
    id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(id),
    account_id TEXT REFERENCES accounts(id),
    category_id TEXT NOT NULL REFERENCES categories(id),
    expected_amount_minor INTEGER NOT NULL,
    moving_avg_amount_minor INTEGER NOT NULL,
    price_creep_threshold_pct REAL NOT NULL DEFAULT 5.0,
    frequency TEXT NOT NULL CHECK (frequency IN ('WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY')),
    expected_day_of_month INTEGER CHECK (expected_day_of_month BETWEEN 1 AND 31),
    next_expected_date DATE NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.9,
    is_mandatory INTEGER NOT NULL DEFAULT 1 CHECK (is_mandatory IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE investment_holdings (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    isin TEXT NOT NULL,
    folio_number TEXT NOT NULL DEFAULT 'DEFAULT',
    instrument_name TEXT NOT NULL,
    asset_class TEXT NOT NULL CHECK (asset_class IN ('EQUITY_MF', 'DEBT_MF', 'HYBRID_MF', 'STOCK', 'ETF', 'GOLD_SGB', 'FD', 'EPF_PPF')),
    units_micro INTEGER NOT NULL, -- 1 unit = 1,000,000 micro-units
    cost_basis_minor INTEGER NOT NULL,
    current_nav_minor INTEGER NOT NULL,
    current_value_minor INTEGER NOT NULL,
    valuation_date DATE NOT NULL,
    valuation_source TEXT NOT NULL DEFAULT 'CAS_PDF',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(account_id, isin, folio_number)
);

CREATE TABLE financial_goals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    linked_account_id TEXT REFERENCES accounts(id),
    target_amount_minor INTEGER NOT NULL CHECK (target_amount_minor > 0),
    current_locked_amount_minor INTEGER NOT NULL DEFAULT 0 CHECK (current_locked_amount_minor >= 0),
    monthly_contribution_minor INTEGER NOT NULL DEFAULT 0,
    target_date DATE,
    priority INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'PAUSED', 'COMPLETED')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ============================================================================
-- 6. ROLLUPS, AI AUDIT & MONOTONIC SYNC CHANGELOG
-- ============================================================================
CREATE TABLE monthly_category_rollups (
    year_month TEXT NOT NULL, -- YYYY-MM
    category_id TEXT NOT NULL REFERENCES categories(id),
    gross_debit_minor INTEGER NOT NULL DEFAULT 0,
    refund_credit_minor INTEGER NOT NULL DEFAULT 0,
    reimbursement_credit_minor INTEGER NOT NULL DEFAULT 0,
    net_expense_minor INTEGER NOT NULL DEFAULT 0,
    tx_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (year_month, category_id)
);

CREATE TABLE ai_requests (
    id TEXT PRIMARY KEY,
    requested_provider TEXT NOT NULL CHECK (requested_provider IN ('LOCAL_OLLAMA', 'CLOUD_GEMINI', 'CLOUD_OPENAI')),
    purpose TEXT NOT NULL,
    consent_signature TEXT, -- Required if requested_provider starts with CLOUD_
    sanitized_payload_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('COMPLETED', 'REJECTED_NO_CONSENT', 'VALIDATION_FAILED', 'PROVIDER_ERROR')),
    latency_ms INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE ai_insights (
    id TEXT PRIMARY KEY,
    ai_request_id TEXT NOT NULL REFERENCES ai_requests(id),
    insight_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    insight_json TEXT NOT NULL,
    source_data_hash TEXT NOT NULL,
    provider TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE server_changelog (
    seq_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_table TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('UPSERT', 'SUPERSEDE')),
    payload_json TEXT NOT NULL,
    origin_device_id TEXT,
    logged_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);


-- ============================================================================
-- 7. LEDGER INTEGRITY TRIGGERS
-- ============================================================================
-- Entries are built as DRAFT, then promoted to POSTED once balanced. Zero-sum is checked at the
-- DRAFT -> POSTED transition (not per line insert, which would reject 3+ line entries mid-insert).

CREATE TRIGGER trg_journal_entry_no_insert_posted
BEFORE INSERT ON journal_entries
WHEN NEW.status != 'DRAFT'
BEGIN
    SELECT RAISE(ABORT, 'LEDGER_INTEGRITY_ERROR: Journal entries must be created as DRAFT and then posted.');
END;

CREATE TRIGGER trg_journal_entry_post_requires_balance
BEFORE UPDATE OF status ON journal_entries
WHEN OLD.status = 'DRAFT' AND NEW.status = 'POSTED'
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM journal_lines WHERE journal_entry_id = OLD.id) < 2
        THEN RAISE(ABORT, 'LEDGER_INTEGRITY_ERROR: A journal entry needs at least two lines to post.')
        WHEN (SELECT SUM(signed_amount_minor) FROM journal_lines WHERE journal_entry_id = OLD.id) != 0
        THEN RAISE(ABORT, 'LEDGER_INTEGRITY_ERROR: Journal lines do not sum to zero.')
    END;
END;

CREATE TRIGGER trg_journal_entry_no_unpost
BEFORE UPDATE OF status ON journal_entries
WHEN OLD.status = 'POSTED' AND NEW.status != 'POSTED'
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABILITY_ERROR: A posted journal entry cannot return to DRAFT; insert a REVERSAL entry instead.');
END;

CREATE TRIGGER trg_journal_lines_no_insert_when_posted
BEFORE INSERT ON journal_lines
WHEN (SELECT status FROM journal_entries WHERE id = NEW.journal_entry_id) = 'POSTED'
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABILITY_ERROR: Lines of a posted journal entry cannot be inserted.');
END;

CREATE TRIGGER trg_journal_lines_no_update_when_posted
BEFORE UPDATE ON journal_lines
WHEN (SELECT status FROM journal_entries WHERE id = OLD.journal_entry_id) = 'POSTED'
  OR (SELECT status FROM journal_entries WHERE id = NEW.journal_entry_id) = 'POSTED'
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABILITY_ERROR: Lines of a posted journal entry cannot be updated.');
END;

-- Direct deletes of a posted entry's lines are always refused, provisional or not. Deleting a
-- provisional entry still cascades: the parent row is already gone when the cascade runs, so
-- this condition is false for cascaded deletes.
CREATE TRIGGER trg_journal_lines_no_delete_when_posted
BEFORE DELETE ON journal_lines
WHEN EXISTS (
    SELECT 1 FROM journal_entries
    WHERE id = OLD.journal_entry_id AND status = 'POSTED'
)
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABILITY_ERROR: Lines of a posted journal entry cannot be deleted.');
END;

CREATE TRIGGER trg_prevent_committed_journal_delete
BEFORE DELETE ON journal_entries
WHEN OLD.is_provisional = 0
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABILITY_ERROR: Committed journal entries cannot be deleted; insert a REVERSAL entry instead.');
END;
