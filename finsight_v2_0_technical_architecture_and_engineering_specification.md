# FINSIGHT v2.0
## Personal Finance Intelligence Platform
### Principal Technical Architecture, Deterministic Double-Entry Ledger, Zero-Trust AI Gateway & Production Engineering Specification

* **Prepared:** 12 November 2026
* **Classification:** Production System Architecture & Client Engineering Blueprint
* **Architecture Paradigm:** Mobile-First, Local-First Modular Monolith with Deterministic Double-Entry Accounting & Privacy-Filtered Hybrid AI

---

## 1. Document Purpose, Product Vision & Architectural Invariants

### 1.1 Executive Product Vision
FinSight is a mobile-first, local-first personal financial intelligence platform engineered for a primary individual user who requires institutional-grade accounting accuracy, seamless mobile accessibility, automated bank and investment statement ingestion, and complete sovereignty over sensitive financial records.

> **Core Product Principle:** Financial records, original PDF/CSV statements, balance calculations, and the authoritative database remain strictly under the user's physical control. Artificial Intelligence operates exclusively as an optional, read-only analytical assistant behind a deterministic privacy gateway; AI is never the source of truth for money.

### 1.2 Architectural Selection Matrix

| Decision Domain | Selected Engineering Direction |
| :--- | :--- |
| **Data Privacy Model** | **Hybrid Zero-Trust:** Raw statements, account identifiers, and transaction-level records never leave the private server. Only explicitly approved, bucketed, and anonymized summaries may be transmitted to cloud AI providers. |
| **Client Platform** | **Mobile-First (iOS & Android):** React Native (Expo Custom Development Build) with an encrypted local SQLCipher replica, offline command queue, and optional local web/admin interface. |
| **Functional Scope** | **Full-Spectrum Wealth & Cash-Flow Management:** Bank accounts, credit cards, P2P split reimbursements, safe-to-spend liquidity, budgets, subscriptions, CAMS/NSDL investments, assets, liabilities, tax tagging, and financial goals. |
| **Intelligence Layer** | **Three-Tier Hybrid Routing:** Deterministic regex rules $\rightarrow$ Local CPU ONNX embeddings (`all-MiniLM-L6-v2`) $\rightarrow$ Optional Local LLM (Ollama) or Consent-Gated Cloud AI (Gemini / OpenAI) disabled by default. |
| **Target Host Hardware** | **Customer Premises Equipment (Windows Host):** Intel Core i7 (8th Gen), 16 GB DDR4 RAM, NVIDIA GTX 1050 Ti (4 GB VRAM), NVMe SSD storage. |

### 1.3 Critical Privacy Distinction
A hybrid AI architecture is not a zero-data-egress system unless cloud providers are disabled. Even aggregated category spending totals can reveal sensitive behavioral patterns through side-channel inference.
* **Strict Zero-Egress Mode:** When absolute data residency is required, the user toggles `CLOUD_AI_ENABLED = false` at the gateway level, restricting the system to deterministic Python financial engines, local ONNX embeddings, and local Ollama models.
* **Provider Retention Governance:** Contractual assurances such as *"not used for model training"* do not imply *"zero data retention"* or *"zero transmission."* Cloud API requests enforce payload rounding (to the nearest $500\text{ INR}$), category redaction, and explicit per-request cryptographic user approval.

### 1.4 The Four Mathematical Invariants of FinSight
To guarantee zero accounting bugs or silent data corruption, every line of code and database schema constraint enforces four non-negotiable laws:
1. **Law of Zero-Sum Conservation:** Every financial mutation is recorded as an immutable double-entry journal entry where the sum of signed minor currency units across all child journal lines equals zero:
   $$\sum_{i=1}^{n} \text{signed\_amount\_minor}_i = 0$$
2. **Law of Integer Monetary Precision:** Binary floating-point types (`FLOAT`, `REAL`, `DOUBLE`, `IEEE 754`) are strictly forbidden for currency storage or arithmetic. All monetary amounts are stored as 64-bit signed integers representing minor currency units ($1\text{ INR} = 100\text{ paise}$). Fractional mutual fund units are stored as integer micro-units ($1\text{ unit} = 10^6\text{ micro-units}$).
3. **Law of Idempotent Ingestion & Sync:** Uploading the same statement file or replaying a mobile synchronization command $N$ times produces the exact same database state and account balances as executing it once.
4. **Law of Read-Only AI Isolation:** Probabilistic models (local LLMs and cloud APIs) have zero write permissions (`INSERT`, `UPDATE`, `DELETE`) on any ledger table and cannot compute authoritative financial totals.

---

## 2. Feature Architecture: Core Baseline & High-Impact Expansions

Beyond foundational account, transaction, and budget tracking, FinSight v2.0 incorporates specialized capabilities tailored for Indian banking workflows, credit card billing cycles, and daily user retention.

### 2.1 Feature Matrix by Engineering Impact

| Tier | Feature Name | Problem Solved | Technical Mechanism |
| :--- | :--- | :--- | :--- |
| **Quick Win** | **Automated PDF Password Vault** | Indian bank and credit card PDFs are almost universally encrypted with static password patterns (e.g., `FIRST4NAME + DDMM` or Customer ID). | Stores per-account AES-256-GCM encrypted password rules; the ingestion worker unlocks PDFs in memory via PyMuPDF automatically upon upload. |
| **Quick Win** | **P2P Split & Reimbursement Sub-Ledger** | Paying for a group dinner and receiving UPI repayments from friends inflates both monthly expenses and false "income." | Routes friend shares into `Account:Asset:Pending_Reimbursements`; incoming UPI credits settle the receivable and leave net dining spend accurate. |
| **Quick Win** | **Tax & Deduction Tagging (`80C`/`80D`/`HRA`)** | Scrambling across 12 months of statements during income tax filing season. | Auto-tags eligible insurance, ELSS mutual funds, rent, and medical transactions with tax sections for one-tap FY summary export. |
| **Core Moat** | **"Safe-to-Spend" Liquidity Engine** | Raw bank balances mislead users when credit card bills, EMIs, and savings goal locks are pending within the next 30 days. | Calculates real-time disposable liquidity and daily safe burn rate after subtracting unbilled/billed card debt, 30-day obligations, and goal locks. |
| **Core Moat** | **CAMS / NSDL CAS Portfolio Ingestion** | Live stock/MF APIs require paid subscriptions or sharing brokerage credentials, violating local-first privacy. | Parses monthly Consolidated Account Statement (CAS) PDFs to update ISIN holdings, cost basis, current valuation, and exact Newton-Raphson XIRR. |
| **Core Moat** | **Cross-Cycle Refund & Settlement Netting** | Merchant refunds distort gross spending, and credit card bill payments risk double-counting expenses. | Automatically pairs refunds to original purchases (netting category spend) and pairs bank debits to credit card credits across a $\pm 3$-day window. |
| **Retention Loop** | **Provisional Real-Time Spend Capture** | Waiting 30 days for a monthly PDF statement renders budget alerts useless until after overspending occurs. | Captures real-time payment notifications on Android/iOS as `PROVISIONAL` entries that automatically merge and upgrade when the official PDF is imported. |
| **Retention Loop** | **Subscription Price-Creep & Renewal Radar** | Silent subscription price hikes and annual renewals debit accounts without warning. | Tracks moving-average merchant charges and triggers local alerts 7 days before renewal or when an amount increases by more than $\tau\%$ (default $5\%$). |

### 2.2 UX & Workflow Optimizations
1. **Statement-First Cold Onboarding:** New users do not manually configure bank metadata or opening balances. Uploading a single PDF statement triggers institution auto-discovery, opening balance extraction, account creation, and historical recurring-rule detection in one step.
2. **Confidence-Tiered Approval Queue:** Instead of forcing the user to manually approve 150 rows every month, transactions with parser/categorizer confidence $\ge 0.95$ and zero running-balance discrepancy are marked `AUTO_APPROVED`. Only new merchants, ambiguous splits, or balance mismatches require human review.
3. **Visual Reconciliation Diff Helper:** If a statement fails balance reconciliation ($\text{Opening} + \text{Credits} - \text{Debits} \neq \text{Closing}$), the UI isolates the exact row where the running balance diverged and displays the cropped PDF table row beside the parsed fields.

---

## 3. Recommended Technology Stack & Resource Envelope

### 3.1 Technology Stack Specification

| Architectural Layer | Selected Technology | Role & Production Engineering Rationale |
| :--- | :--- | :--- |
| **Mobile Client** | React Native + Expo (Custom Dev Build) + TypeScript | Unified iOS/Android codebase; custom native build compiles native `SQLCipher` and Android `NotificationListenerService`. |
| **Mobile Charts & UI** | Victory Native XL (Skia) + FlashList | 60 FPS GPU-accelerated financial charts and virtualized transaction lists capable of rendering 50,000+ rows smoothly. |
| **Backend API & Engine** | Python 3.12 + FastAPI + Pydantic v2 | Strictly typed, high-throughput REST endpoints, deterministic accounting logic, and asynchronous job dispatch. |
| **Authoritative Database** | SQLite 3 + SQLCipher (WAL Mode) | AES-256 encrypted single-user relational ledger with zero network attack surface and microsecond local read latency. |
| **ORM & Migrations** | SQLAlchemy 2.0 + Alembic | Strongly typed data access layer with repeatable, version-controlled schema migrations. |
| **PDF & Table Extraction** | PyMuPDF (`fitz`) + `pdfplumber` | High-speed extraction of native text streams, character bounding boxes, and vector table gridlines. |
| **Local OCR Engine** | RapidOCR (ONNX Runtime) | Replaces legacy Tesseract; uses lightweight PaddleOCR models compiled to ONNX for fast, accurate multi-column table OCR on CPU. |
| **Merchant Categorization** | `all-MiniLM-L6-v2` (ONNX Runtime) | 80 MB quantized sentence-transformer running on CPU in $<8\text{ ms/row}$, eliminating LLM VRAM usage for routine categorization. |
| **Local AI Inference** | Ollama (`Llama-3.2-3B-Instruct-Q4_K_M`) | Optional local conversational assistant running on GTX 1050 Ti with a strict 2-minute keep-alive auto-unload policy. |
| **Cloud AI Providers** | Google Gemini 2.5 Flash / OpenAI API | Optional complex scenario reasoning using strictly bucketed, PII-free JSON payloads after explicit per-request user consent. |
| **Private Mesh Network** | Tailscale (WireGuard) + Caddy HTTPS | Zero-config point-to-point encrypted mesh VPN with automated TLS certificates; zero open router ports. |
| **Container & Backup Stack** | Docker Compose (WSL2) + `age` + `rclone` | Reproducible service isolation, strict memory caps, public-key backup encryption, and automated offsite cloud replication. |

### 3.2 Hardware Resource Allocation (Intel i7 8th Gen / 16 GB RAM / GTX 1050 Ti 4 GB)
Running Windows 10/11 alongside WSL2, Docker, OCR workers, and local LLMs will exhaust 16 GB of system memory if left unbounded. FinSight enforces strict container cgroup limits:

| Container / Subsystem | CPU Limit | RAM Limit | VRAM Allocation | Lifecycle Policy |
| :--- | :--- | :--- | :--- | :--- |
| **`finsight_api` (FastAPI + SQLCipher + ONNX)** | 2.0 Cores | 512 MB | 0 MB | Always-On Daemon |
| **`finsight_pdf_worker` (PyMuPDF + RapidOCR)** | 3.0 Cores | 1536 MB | 0 MB | Sandboxed Worker Pool |
| **`finsight_ollama` (Local 3B Quantized LLM)** | 2.0 Cores | 3584 MB | $\le 3.2\text{ GB}$ (GTX 1050 Ti) | On-Demand (`OLLAMA_KEEP_ALIVE=2m`) |
| **`finsight_backup` (`age` + `rclone` Cron)** | 1.0 Core | 256 MB | 0 MB | Scheduled Nightly Execution |
| **Total WSL2 Host Allocation (`.wslconfig`)** | **6.0 Cores** | **8192 MB Hard Cap** | **Shared WDDM** | Leaves 8 GB RAM exclusively for Windows OS |

---

## 4. End-to-End System Architecture & Network Topology

### 4.1 System Architecture Diagram

```text
+---------------------------------------------------------------------------------------+
|                      MOBILE APPLICATION (iOS / Android - Expo Dev Build)              |
|                                                                                       |
|  +-----------------------+  +-------------------------+  +-------------------------+  |
|  | Screens & Skia Charts |  | Provisional Capture     |  | Biometrics & KeyStore   |  |
|  | - Safe-to-Spend Gauge |  | - Android Notification  |  | - Hardware-Backed DEK   |  |
|  | - Diff Review Queue   |  | - iOS Payment Shortcut  |  | - mTLS Device Identity  |  |
|  +-----------+-----------+  +------------+------------+  +------------+------------+  |
|              |                           |                            |               |
|              v                           v                            v               |
|  +---------------------------------------------------------------------------------+  |
|  | Encrypted Mobile Replica (SQLCipher) + FIFO Command Outbox + Sync Cursor        |  |
|  +---------------------------------------+-----------------------------------------+  |
+------------------------------------------|--------------------------------------------+
                                           |
                                           | HTTPS over Private Tailscale WireGuard Mesh
                                           | + Wake-on-LAN (UDP Magic Packet Relay)
                                           v
+---------------------------------------------------------------------------------------+
|                   PRIVATE HOME SERVER (Windows Host / WSL2 / Docker Compose)          |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | FastAPI Gateway (`/api/v1`)                                                     |  |
|  | - JWT & Device Registry  - Idempotency Guard  - Rate Limiter  - Sync Engine     |  |
|  +-------+------------------------------------+---------------------------------+--+  |
|          |                                    |                                 |     |
|          v                                    v                                 v     |
|  +-------------------------------+  +-------------------------------+  +-----------+  |
|  | Air-Gapped Ingestion Worker   |  | Deterministic Finance Engine  |  | AI Privacy|  |
|  | 1. File SHA-256 & MIME Guard  |  | - Double-Entry Journal Core   |  | Gateway   |  |
|  | 2. PDF Password Vault Unlock  |  | - Safe-to-Spend Calculator    |  | - Consent |  |
|  | 3. Layout Drift Fingerprinter |  | - Transfer & Card Linker      |  |   Ledger  |  |
|  | 4. PyMuPDF / RapidOCR Engine  |  | - Refund & P2P Split Netting  |  | - 500 INR |  |
|  | 5. UPI/IMPS/NEFT Normalizer   |  | - Subscription Creep Detector |  |   Bucketer|  |
|  | 6. ONNX Vector Categorizer    |  | - CAS Portfolio & XIRR Engine |  | - Schema  |  |
|  | 7. Row-by-Row Balance Verifier|  +---------------+---------------+  |   Guard   |  |
|  +---------------+---------------+                  |                  +-----+-----+  |
|                  |                                  v                        |        |
|                  |                  +-------------------------------+        |        |
|                  +----------------->| Authoritative SQLCipher DB    |        |        |
|                                     | - Zero-Sum Journal Triggers   |        |        |
|                                     | - Materialized Rollup Tables  |        |        |
|                                     | - Monotonic Server Changelog  |        |        |
|                                     +---------------+---------------+        |        |
|                                                     |                        |        |
|                                                     v                        v        |
|                                     +-------------------------------+  +-----------+  |
|                                     | 3-2-1 Encrypted Backup Worker |  | Ollama GPU|  |
|                                     | - SQLCipher VACUUM INTO       |  | or Cloud  |  |
|                                     | - Canary Integrity Verifier   |  | Gemini /  |  |
|                                     | - Age X25519 + Rclone Offsite |  | OpenAI API|  |
|                                     +-------------------------------+  +-----------+  |
+---------------------------------------------------------------------------------------+
```

### 4.2 Network Boundaries & Remote Power Availability
* **Zero Public Exposure:** Only the FastAPI HTTPS port (`8443`) binds to the host's private Tailscale IP (`100.x.y.z`). SQLCipher database files, internal IPC queues, and the Ollama inference port (`11434`) bind exclusively to internal Docker bridge networks with outbound internet disabled where appropriate.
* **Solving Host PC Sleep (Wake-on-LAN + Offline Queue):**
  1. When the mobile app is used while the Windows PC is in S3 sleep, all read operations (dashboards, search, net worth, safe-to-spend) execute instantaneously against the local mobile SQLCipher replica.
  2. All write operations (manual expenses, category edits, provisional captures) append to the local `sync_outbox` table.
  3. If an always-on low-power Tailscale peer (such as an Apple TV, home router, or Raspberry Pi) is present on the LAN, the mobile client sends a signed Wake-on-LAN request to wake the Windows PC remotely before uploading statement PDFs.

---

## 5. Backend Modules & Domain Responsibilities

| Module | Primary Engineering Responsibilities |
| :--- | :--- |
| **1. Authentication & Device Registry** | Argon2id password verification, Ed25519/ECDSA device key registration, short-lived JWT access tokens, refresh token rotation, and instant remote revocation for lost phones. |
| **2. Account & Card Cycle Manager** | CRUD for bank, credit card, cash, loan, investment, and virtual clearing accounts; manages billing cycle days, payment due dates, credit limits, and encrypted PDF password rules. |
| **3. Statement Vault & Provenance** | Multipart upload streaming, MIME signature validation, SHA-256 file deduplication, AES-256-GCM raw document encryption, and parser provenance tracking. |
| **4. Document Parser & Drift Guard** | Automated PDF decryption, header layout fingerprinting (detecting bank format changes), PyMuPDF text/table extraction, RapidOCR fallback, and institution-specific row parsing. |
| **5. Narration Normalizer & Deduplicator** | Deterministic regex extraction of UPI VPAs, 12-digit UTR/RRN numbers, IMPS/NEFT references, provisional-to-authoritative transaction merging, and SHA-256 fingerprint generation. |
| **6. Hybrid Categorization Engine** | Three-stage resolution: (1) Exact VPA/merchant rule match, (2) Regex alias match, (3) Local CPU ONNX `all-MiniLM-L6-v2` cosine similarity against known merchant embeddings, plus automated rule learning from user corrections. |
| **7. Double-Entry Ledger Engine** | Atomic construction of `journal_entries` and balanced `journal_lines`, internal transfer pairing, credit card bill settlement linking, refund netting, and P2P split reimbursement accounting. |
| **8. Liquidity & Budget Engine** | Real-time calculation of `SafeToSpend`, daily safe burn rate, monthly/category budget utilization, discretionary vs. mandatory spend ratios, and threshold breach alerts. |
| **9. Recurring & Price-Creep Engine** | Time-series periodicity detection for subscriptions, EMIs, utilities, and insurance premiums; flags silent price increases exceeding user thresholds and upcoming renewal dates. |
| **10. Wealth, CAS & XIRR Engine** | CAMS/NSDL CAS PDF ingestion, ISIN portfolio valuation tracking, physical asset/liability depreciation/appreciation snapshots, net-worth history, and Newton-Raphson XIRR calculation. |
| **11. Tax & Compliance Engine** | Automated and manual mapping of transactions and investments to tax sections (`80C`, `80D`, `80CCD`, `HRA`, `24B`, `LTCG`, `STCG`) with fiscal-year audit report generation. |
| **12. Zero-Trust AI Gateway** | Intent routing, differential privacy bucketing ($\pm 500\text{ INR}$), sensitive category redaction, cryptographic user consent verification, Ollama lifecycle management, and Pydantic output validation. |
| **13. CQRS Sync Engine** | Upstream processing of mobile `sync_outbox` commands with idempotency keys and optimistic concurrency checks; downstream streaming of `server_changelog` delta sequences. |

---

## 6. Production Database Design & Double-Entry Ledger Schema

### 6.1 Double-Entry Accounting Mapping Matrix
To eliminate double-counting across transfers, credit cards, refunds, and group splits, every transaction maps to strict debit ($+$) and credit ($-$) journal lines:

| Financial Event | Debit Account ($+\text{Amount}$) | Credit Account ($-\text{Amount}$) | Net Impact on Income / Expense Rollups |
| :--- | :--- | :--- | :--- |
| **Standard Bank/UPI Expense** | `EXPENSE:{Category}` ($+50000$) | `ASSET:{Bank_Savings}` ($-50000$) | $+\text{500.00 INR}$ Category Expense |
| **Credit Card Purchase** | `EXPENSE:{Category}` ($+200000$) | `LIABILITY:{Credit_Card}` ($-200000$) | $+\text{2,000.00 INR}$ Category Expense |
| **Credit Card Bill Payment** | `LIABILITY:{Credit_Card}` ($+200000$) | `ASSET:{Bank_Savings}` ($-200000$) | **$0.00\text{ INR}$** (Pure Liability Settlement) |
| **Own-Account Transfer** | `ASSET:{Bank_B}` ($+1000000$) | `ASSET:{Bank_A}` ($-1000000$) | **$0.00\text{ INR}$** (Pure Asset Reallocation) |
| **Merchant Refund (Credit)** | `ASSET:{Bank_or_Card}` ($+50000$) | `EXPENSE:{Original_Category}` ($-50000$) | $-\text{500.00 INR}$ Offset against Category Spend |
| **Group Split ($1,200\text{ INR}$, 3 ways)** | `EXPENSE:{Dining}` ($+40000$) & `ASSET:{Pending_Reimbursements}` ($+80000$) | `ASSET:{Bank_Savings}` ($-120000$) | $+\text{400.00 INR}$ True User Expense |
| **Friend UPI Repayment ($400\text{ INR}$)** | `ASSET:{Bank_Savings}` ($+40000$) | `ASSET:{Pending_Reimbursements}` ($-40000$) | **$0.00\text{ INR}$** (Settles Receivable Asset) |

### 6.2 Complete SQLCipher DDL Schema (`schema.sql`)

```sql
-- Enable Write-Ahead Logging and strict relational integrity
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;

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
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE journal_lines (
    id TEXT PRIMARY KEY,
    journal_entry_id TEXT NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    signed_amount_minor INTEGER NOT NULL, -- Positive = DEBIT, Negative = CREDIT
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
CREATE TRIGGER trg_validate_journal_zero_sum
AFTER INSERT ON journal_lines
BEGIN
    SELECT CASE
        WHEN (
            SELECT COUNT(*) FROM journal_lines WHERE journal_entry_id = NEW.journal_entry_id
        ) >= 2
        AND (
            SELECT TOTAL(signed_amount_minor) FROM journal_lines WHERE journal_entry_id = NEW.journal_entry_id
        ) != 0
        THEN RAISE(ABORT, 'LEDGER_INTEGRITY_ERROR: Journal lines do not sum to zero.')
    END;
END;

CREATE TRIGGER trg_prevent_committed_journal_delete
BEFORE DELETE ON journal_entries
WHEN OLD.is_provisional = 0
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABILITY_ERROR: Committed journal entries cannot be deleted; insert a REVERSAL entry instead.');
END;
```

---

## 7. Deterministic Statement Ingestion, Decryption & Reconciliation Pipeline

### 7.1 16-Stage Ingestion State Machine
1. **Upload & Size/MIME Validation:** Reject files $>25\text{ MB}$ or lacking valid `%PDF-1.` / UTF-8 CSV signatures.
2. **SHA-256 File Hash Check:** Compute `file_hash_sha256` immediately. If present in `statements`, return `409 DUPLICATE_STATEMENT` to prevent double imports.
3. **Automated Password Vault Unlock:** Fetch the account's `encrypted_pdf_password` rule, decrypt in memory, and unlock the PDF stream via `fitz.Document.authenticate()`.
4. **Encrypted Document Storage:** Store the unlocked raw file in `/var/lib/finsight/docs` encrypted at rest with a unique AES-256-GCM key.
5. **Layout Fingerprinting (Format Drift Guard):** Compute a deterministic hash of the normalized table headers and X-axis column spans on Page 1. If a bank silently changes its PDF layout, halt parsing immediately rather than importing swapped Debit/Credit columns.
6. **Text & Table Extraction:** Extract text blocks and table coordinates via PyMuPDF; if a page contains scanned images ($<40$ selectable characters), invoke the local ONNX `RapidOCR` worker.
7. **Institution-Specific Parser Execution:** Route to `SBIParser`, `HDFCParser`, `ICICIParser`, `AxisParser`, or `CASParser`.
8. **Multi-Line Description Stitching:** Merge continuation lines (rows with empty date and amount columns) into the parent transaction's description buffer.
9. **UPI / IMPS / NEFT Regex Normalization:** Strip routing prefixes and extract the canonical VPA, counterparty name, and 12-digit UTR/RRN reference.
10. **Row-by-Row Running Balance Verification:** For every row $i \in \{1 \dots N\}$, verify:
    $$B_i = B_{i-1} + \text{Credit}_i - \text{Debit}_i$$
    If $B_i \neq \text{StatedBalance}_i$, log an `import_errors` diagnostic pinpointing the exact row $i$.
11. **Deduplication & Provisional Merge:** Check `external_reference` (UTR) and `dedup_fingerprint`. If a matching `PROVISIONAL` entry exists from mobile notifications, upgrade it in place while preserving user notes and splits.
12. **Two-Tier Merchant & Category Matching:** Match against exact VPA and regex aliases first; for unknown strings, compute a 384-dim embedding using ONNX `all-MiniLM-L6-v2` and match if cosine similarity $\ge 0.82$.
13. **Transfer, Card Settlement & Refund Pairing:** Identify internal transfers, credit card bill payments, and merchant refunds across a $\pm 3$-day window.
14. **Confidence-Tiered Queue Routing:** Rows with zero balance discrepancy and confidence $\ge 0.95$ are marked `AUTO_APPROVED`; remaining rows enter `PENDING_REVIEW`.
15. **Transactional Double-Entry Commit:** Upon approval, write `journal_entries`, `journal_lines`, and `transactions` inside a single SQLite `BEGIN IMMEDIATE` transaction.
16. **Rollup & Sync Changelog Publication:** Update `monthly_category_rollups`, `account_balance_snapshots`, and append deltas to `server_changelog`.

### 7.2 Production Ingestion Code: Password Vault, Drift Guard & UPI Normalizer

```python
import re
import hashlib
import fitz  # PyMuPDF
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class StatementSecurityAndDriftError(Exception):
    """Raised when PDF decryption fails or bank column layout drifts."""


class PDFPasswordVault:
    """Decrypts stored account PDF passwords and unlocks protected Indian bank statements."""

    def __init__(self, master_aes_key: bytes):
        if len(master_aes_key) != 32:
            raise ValueError("Master key must be exactly 32 bytes for AES-256-GCM.")
        self._aesgcm = AESGCM(master_aes_key)

    def encrypt_password_rule(self, plaintext_password: str, nonce_12b: bytes) -> str:
        ciphertext = self._aesgcm.encrypt(nonce_12b, plaintext_password.encode("utf-8"), None)
        return (nonce_12b + ciphertext).hex()

    def decrypt_password_rule(self, encrypted_hex: str) -> str:
        raw = bytes.fromhex(encrypted_hex)
        nonce, ciphertext = raw[:12], raw[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

    def open_and_unlock_pdf(
        self, pdf_bytes: bytes, encrypted_password_hex: Optional[str], fallback_candidates: List[str]
    ) -> fitz.Document:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if not doc.is_encrypted:
            return doc

        passwords_to_try: List[str] = []
        if encrypted_password_hex:
            passwords_to_try.append(self.decrypt_password_rule(encrypted_password_hex))
        passwords_to_try.extend(fallback_candidates)

        for candidate in passwords_to_try:
            if doc.authenticate(candidate) > 0:
                return doc

        raise StatementSecurityAndDriftError("PDF_DECRYPTION_FAILED: No configured password unlocked the statement.")


@dataclass(frozen=True)
class RawParsedRow:
    row_index: int
    page_number: int
    tx_date: date
    raw_description: str
    debit_minor: int
    credit_minor: int
    stated_running_balance_minor: Optional[int]


@dataclass(frozen=True)
class NormalizedTransactionCandidate:
    row_index: int
    tx_date: date
    raw_description: str
    clean_description: str
    channel: str
    extracted_vpa: Optional[str]
    external_utr: Optional[str]
    amount_minor: int
    direction: str  # 'DEBIT' or 'CREDIT'
    dedup_fingerprint: str
    balance_verified: bool


class IndianBankingNormalizer:
    """Deterministic regex normalizer for HDFC, SBI, ICICI, and Axis narrations."""

    UPI_PATTERNS = [
        re.compile(
            r"UPI[-/](?:DR|CR)?[-/]?(?P<utr>\d{12})[-/](?P<merchant>[^-/]+)[-/](?:[A-Z]{4}\d*[-/])?(?P<vpa>[a-zA-Z0-9.\-_]+@[a-zA-Z0-9]+)",
            re.IGNORECASE,
        ),
        re.compile(
            r"UPI[-/](?P<merchant>[^-/]+)[-/](?P<vpa>[a-zA-Z0-9.\-_]+@[a-zA-Z0-9]+)[-/][A-Z0-9]+[-/](?P<utr>\d{12})",
            re.IGNORECASE,
        ),
    ]
    IMPS_PATTERN = re.compile(
        r"IMPS[-/](?:P2A|P2P|RIB|MMT)?[-/]?(?P<utr>\d{12})[-/](?P<merchant>[^-/]+)",
        re.IGNORECASE,
    )
    NEFT_PATTERN = re.compile(
        r"(?P<channel>NEFT|RTGS)[-/](?P<utr>[A-Z]{4}[A-Z0-9]{8,18})[-/](?P<merchant>[^-/]+)",
        re.IGNORECASE,
    )
    CORP_NOISE = re.compile(
        r"\b(PVT|LTD|LIMITED|PRIVATE|INDIA|PAYMENTS?|SOLUTIONS|SERVICES|BANGALORE|MUMBAI|DELHI|POS|SI)\b",
        re.IGNORECASE,
    )

    @classmethod
    def normalize_and_verify_rows(
        cls,
        account_id: str,
        opening_balance_minor: int,
        closing_balance_minor: int,
        raw_rows: List[RawParsedRow],
    ) -> Tuple[List[NormalizedTransactionCandidate], int, List[Tuple[int, int, int]]]:
        """
        Normalizes rows and performs row-by-row running balance verification.
        Returns (candidates, final_computed_balance, list_of_mismatches[(row_idx, expected, actual)]).
        """
        running_balance = opening_balance_minor
        candidates: List[NormalizedTransactionCandidate] = []
        mismatches: List[Tuple[int, int, int]] = []

        for row in raw_rows:
            running_balance = running_balance + row.credit_minor - row.debit_minor
            row_balance_ok = True
            if row.stated_running_balance_minor is not None:
                if running_balance != row.stated_running_balance_minor:
                    row_balance_ok = False
                    mismatches.append((row.row_index, running_balance, row.stated_running_balance_minor))
                    # Re-anchor to stated balance so a single row error doesn't cascade false positives
                    running_balance = row.stated_running_balance_minor

            direction = "DEBIT" if row.debit_minor > 0 else "CREDIT"
            amount_minor = row.debit_minor if row.debit_minor > 0 else row.credit_minor

            collapsed = " ".join(row.raw_description.strip().split())
            channel = "OTHER"
            vpa: Optional[str] = None
            utr: Optional[str] = None
            merchant_raw = collapsed

            for upi_re in cls.UPI_PATTERNS:
                m = upi_re.search(collapsed)
                if m:
                    channel = "UPI"
                    vpa = m.group("vpa").lower()
                    utr = m.group("utr")
                    merchant_raw = m.group("merchant")
                    break

            if channel == "OTHER":
                m_imps = cls.IMPS_PATTERN.search(collapsed)
                if m_imps:
                    channel = "IMPS"
                    utr = m_imps.group("utr")
                    merchant_raw = m_imps.group("merchant")

            if channel == "OTHER":
                m_neft = cls.NEFT_PATTERN.search(collapsed)
                if m_neft:
                    channel = m_neft.group("channel").upper()
                    utr = m_neft.group("utr")
                    merchant_raw = m_neft.group("merchant")

            cleaned = cls.CORP_NOISE.sub("", merchant_raw)
            cleaned = re.sub(r"[^a-zA-Z0-9\s&]", " ", cleaned)
            cleaned = " ".join(cleaned.upper().split()) or collapsed[:32].upper()

            fp_seed = (
                f"{account_id}|{direction}|{amount_minor}|UTR:{utr}"
                if utr
                else f"{account_id}|{row.tx_date.isoformat()}|{direction}|{amount_minor}|{cleaned[:24]}"
            )
            dedup_fp = hashlib.sha256(fp_seed.encode("utf-8")).hexdigest()

            candidates.append(
                NormalizedTransactionCandidate(
                    row_index=row.row_index,
                    tx_date=row.tx_date,
                    raw_description=collapsed,
                    clean_description=cleaned,
                    channel=channel,
                    extracted_vpa=vpa,
                    external_utr=utr,
                    amount_minor=amount_minor,
                    direction=direction,
                    dedup_fingerprint=dedup_fp,
                    balance_verified=row_balance_ok,
                )
            )

        return candidates, running_balance, mismatches
```

---

## 8. Core Financial Intelligence & Mathematical Engines

### 8.1 Double-Entry Ledger Service & Split Reimbursement Engine

```python
import uuid
import sqlite3
from datetime import date
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class SplitShareSpec:
    counterparty_name: str
    counterparty_vpa: Optional[str]
    owed_amount_minor: int


class DoubleEntryLedgerService:
    """
    Authoritative transactional engine ensuring every expense, transfer, card payment,
    refund, and friend split obeys the zero-sum double-entry invariant.
    """

    def __init__(self, conn: sqlite3.Connection, reimbursement_clearing_account_id: str):
        self.conn = conn
        self.clearing_account_id = reimbursement_clearing_account_id

    def record_expense_with_optional_splits(
        self,
        idempotency_key: str,
        tx_date: date,
        source_account_id: str,
        expense_category_id: str,
        expense_ledger_account_id: str,
        total_amount_minor: int,
        raw_description: str,
        clean_description: str,
        dedup_fingerprint: str,
        splits: Optional[List[SplitShareSpec]] = None,
        statement_id: Optional[str] = None,
        external_reference: Optional[str] = None,
    ) -> str:
        splits = splits or []
        total_reimbursable_minor = sum(s.owed_amount_minor for s in splits)
        if total_reimbursable_minor >= total_amount_minor:
            raise ValueError("Reimbursable split sum cannot exceed total transaction amount.")

        user_share_minor = total_amount_minor - total_reimbursable_minor
        journal_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO journal_entries (id, entry_date, entry_type, source_statement_id, idempotency_key)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    journal_id,
                    tx_date.isoformat(),
                    "SPLIT_EXPENSE" if splits else "STANDARD",
                    statement_id,
                    idempotency_key,
                ),
            )

            # 1. Credit the funding bank or credit card account (-total_amount_minor)
            self.conn.execute(
                """
                INSERT INTO journal_lines (id, journal_entry_id, account_id, signed_amount_minor, memo)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), journal_id, source_account_id, -total_amount_minor, clean_description),
            )

            # 2. Debit the user's true expense category share (+user_share_minor)
            self.conn.execute(
                """
                INSERT INTO journal_lines (id, journal_entry_id, account_id, signed_amount_minor, memo)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), journal_id, expense_ledger_account_id, user_share_minor, "User share"),
            )

            # 3. If split with friends, debit the Pending Reimbursements clearing asset (+total_reimbursable_minor)
            if total_reimbursable_minor > 0:
                self.conn.execute(
                    """
                    INSERT INTO journal_lines (id, journal_entry_id, account_id, signed_amount_minor, memo)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        journal_id,
                        self.clearing_account_id,
                        total_reimbursable_minor,
                        "Pending friend reimbursements",
                    ),
                )

            # 4. Insert primary transaction record
            self.conn.execute(
                """
                INSERT INTO transactions (
                    id, journal_entry_id, account_id, counterparty_account_id, statement_id,
                    category_id, transaction_date, description, clean_description,
                    external_reference, dedup_fingerprint, amount_minor, user_share_minor,
                    direction, transaction_type, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DEBIT', 'EXPENSE', 'USER_APPROVED')
                """,
                (
                    tx_id,
                    journal_id,
                    source_account_id,
                    expense_ledger_account_id,
                    statement_id,
                    expense_category_id,
                    tx_date.isoformat(),
                    raw_description,
                    clean_description,
                    external_reference,
                    dedup_fingerprint,
                    total_amount_minor,
                    user_share_minor,
                ),
            )

            # 5. Track individual friend split receivables
            for split in splits:
                self.conn.execute(
                    """
                    INSERT INTO reimbursable_splits (
                        id, transaction_id, counterparty_name, counterparty_vpa, owed_amount_minor, status
                    ) VALUES (?, ?, ?, ?, ?, 'OPEN')
                    """,
                    (
                        str(uuid.uuid4()),
                        tx_id,
                        split.counterparty_name,
                        split.counterparty_vpa,
                        split.owed_amount_minor,
                    ),
                )

        return tx_id
```

### 8.2 "Safe-to-Spend" Liquidity & Newton-Raphson XIRR Engines

```python
from datetime import date
from typing import List, Tuple


def calculate_safe_to_spend_minor(
    liquid_bank_balances_minor: int,
    unpaid_credit_card_balances_minor: int,
    upcoming_30d_mandatory_obligations_minor: int,
    active_goal_locks_minor: int,
    days_remaining_in_month: int,
) -> dict:
    """
    Computes true disposable cash in minor units (paise) after subtracting
    all unpaid credit card debt, upcoming 30-day EMIs/bills, and locked savings goals.
    """
    net_disposable_minor = (
        liquid_bank_balances_minor
        - abs(unpaid_credit_card_balances_minor)
        - upcoming_30d_mandatory_obligations_minor
        - active_goal_locks_minor
    )
    safe_to_spend = max(0, net_disposable_minor)
    safe_daily = safe_to_spend // max(1, days_remaining_in_month)
    return {
        "liquid_cash_minor": liquid_bank_balances_minor,
        "card_liability_minor": abs(unpaid_credit_card_balances_minor),
        "upcoming_obligations_minor": upcoming_30d_mandatory_obligations_minor,
        "goal_locks_minor": active_goal_locks_minor,
        "safe_to_spend_minor": safe_to_spend,
        "daily_safe_burn_minor": safe_daily,
        "is_liquidity_deficit": net_disposable_minor < 0,
        "deficit_minor": abs(min(0, net_disposable_minor)),
    }


def compute_portfolio_xirr(cashflows: List[Tuple[date, int]], max_iterations: int = 100) -> float:
    """
    Computes exact annualized Internal Rate of Return (XIRR) using Newton-Raphson
    over dated cashflows [(date, signed_amount_minor)], where investments are negative
    and current CAS portfolio valuation is positive.
    """
    if not cashflows or len(cashflows) < 2:
        return 0.0

    t0 = min(cf[0] for cf in cashflows)
    years = [(cf[0] - t0).days / 365.0 for cf in cashflows]
    amounts = [cf[1] / 100.0 for cf in cashflows]

    rate = 0.12  # Initial guess: 12% p.a.
    for _ in range(max_iterations):
        f_val = 0.0
        f_deriv = 0.0
        for amt, yr in zip(amounts, years):
            base = max(1e-6, 1.0 + rate)
            discount = base ** yr
            f_val += amt / discount
            if yr != 0.0:
                f_deriv -= (yr * amt) / (discount * base)

        if abs(f_val) < 1e-5:
            return round(rate * 100.0, 2)
        if abs(f_deriv) < 1e-9:
            break
        rate = rate - (f_val / f_deriv)

    return round(rate * 100.0, 2)
```

---

## 9. Hybrid AI Architecture, ONNX Categorizer & Privacy Gateway

### 9.1 Task Routing Matrix

| Analytical Task | Execution Engine | Hardware Used | Why This Engine Is Selected |
| :--- | :--- | :--- | :--- |
| **Known Merchant & VPA Classification** | Deterministic Hash & Regex Lookup | Host CPU | $<1\text{ ms}$ execution, $100\%$ deterministic, zero memory overhead. |
| **Ambiguous Merchant Categorization** | Local ONNX `all-MiniLM-L6-v2` Embeddings | Host CPU | $80\text{ MB}$ RAM footprint, $5\text{ ms}$ latency, frees GTX 1050 Ti VRAM. |
| **Balances, Safe-to-Spend, Net Worth, XIRR** | Python Deterministic Finance Engine | Host CPU | LLMs are forbidden from performing authoritative monetary arithmetic. |
| **Subscription & Price-Creep Detection** | Python Time-Series Rule Engine | Host CPU | Deterministic interval and moving-average threshold checks. |
| **Offline Natural-Language Spending Q&A** | Local Ollama (`Llama-3.2-3B-Instruct-Q4_K_M`) | GTX 1050 Ti ($4\text{ GB}$ VRAM) | Zero data egress; translates user question into pre-approved read-only SQL query templates. |
| **Multi-Month Coaching & Scenario Analysis** | Optional Cloud AI (Gemini 2.5 Flash / OpenAI) | Remote Cloud API | Rich reasoning over bucketed ($\pm 500\text{ INR}$), PII-stripped summary JSON after explicit user signature. |

### 9.2 Zero-Trust Privacy Sanitizer & Provider Abstraction

```python
import hashlib
import json
from typing import Dict, Any, Set
from pydantic import BaseModel, Field


class AIInsightResponseSchema(BaseModel):
    summary_headline: str = Field(..., max_length=160)
    key_observations: list[str] = Field(..., max_length=5)
    recommended_actions: list[str] = Field(..., max_length=4)
    disclaimer: str = Field(default="Advisory insight only; verified against local deterministic ledger.")


class ZeroTrustPrivacyGateway:
    """
    Sanitizes financial context before any cloud AI call:
    1. Strips all account numbers, dates of birth, raw narrations, and merchant names.
    2. Masks user-designated sensitive categories into 'Redacted_Private'.
    3. Rounds all monetary values to the nearest 500 INR (50,000 paise) bucket.
    """

    BUCKET_PAISE = 500_00  # 500 INR

    @classmethod
    def _round_to_bucket_inr(cls, amount_minor: int) -> int:
        bucketed_minor = int(round(amount_minor / cls.BUCKET_PAISE) * cls.BUCKET_PAISE)
        return bucketed_minor // 100

    @classmethod
    def build_cloud_safe_payload(
        cls,
        year_month: str,
        income_minor: int,
        category_spend_minor: Dict[str, int],
        sensitive_categories: Set[str],
    ) -> Tuple[Dict[str, Any], str]:
        safe_categories: Dict[str, int] = {}
        redacted_sum_minor = 0

        for cat_name, spend_minor in category_spend_minor.items():
            if cat_name in sensitive_categories:
                redacted_sum_minor += spend_minor
            else:
                safe_categories[cat_name] = cls._round_to_bucket_inr(spend_minor)

        if redacted_sum_minor > 0:
            safe_categories["Redacted_Private"] = cls._round_to_bucket_inr(redacted_sum_minor)

        payload = {
            "period": year_month,
            "currency": "INR",
            "bucket_resolution_inr": 500,
            "approximate_monthly_income_inr": cls._round_to_bucket_inr(income_minor),
            "category_expenses_inr": safe_categories,
        }
        canonical_json = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        return payload, payload_hash
```

---

## 10. Mobile Application Architecture & Offline-First Synchronization

### 10.1 Mobile Navigation & Screen Capabilities
The React Native (Expo Custom Dev Build) client uses a 5-tab bottom navigation structure designed for sub-second task completion:
1. **Home (Command Center):** Displays the **Safe-to-Spend** gauge, daily safe burn rate, net worth card, cash-flow trend chart, and active review alerts.
2. **Transactions & Review Queue:** Instant FlashList search across 50,000+ local rows, confidence-tiered import approval queue, visual balance-diff inspector, split-expense tagger, and receipt/statement link viewer.
3. **Accounts, Cards & Splits:** Bank balances, credit card utilization bars, billing cycle grace-period countdowns, statement upload dropzone, and open P2P friend reimbursement tracker.
4. **Plan & Wealth (Budgets / Recurring / CAS):** Category budget bars, subscription renewal calendar with price-creep badges, CAMS/NSDL portfolio allocation, XIRR scorecard, and goal locks.
5. **AI Assistant & Privacy Center:** Conversational Q&A toggleable between Local Ollama and Cloud AI, live JSON payload preview modal prior to cloud transmission, device management, and backup status.

### 10.2 CQRS Command-Outbox & Monotonic Cursor Sync Protocol
To eliminate offline merge corruption, the mobile replica never overwrites server rows blindly:
* **Local Encrypted Storage:** Uses `expo-sqlite` compiled with `SQLCipher`. The 256-bit encryption key is generated inside the iOS Secure Enclave Keychain / Android Keystore (`BIOMETRIC_CURRENT_SET`).
* **Upstream Command Outbox (`POST /api/v1/sync/push`):** Offline edits are stored in a local FIFO table `local_command_outbox (cmd_id, command_type, entity_id, base_version, payload_json)`. Upon reconnecting to Tailscale, commands are pushed in batch. If `base_version < server_version`, the server returns the authoritative record alongside the conflict so the user can accept or override in one tap.
* **Downstream Cursor Pull (`GET /api/v1/sync/pull?after_seq={last_seq_id}`):** The mobile client pulls all `server_changelog` entries where `seq_id > last_seq_id`, applies them inside a single local SQLite transaction, and advances its cursor.

---

## 11. Complete REST API Specification (`/api/v1`)

| Method | Endpoint | Idempotent | Purpose & Security Contract |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/device-register` | Yes | Registers mobile device public key and issues rotated refresh token. |
| `POST` | `/api/v1/auth/device-revoke` | Yes | Immediately revokes a lost or replaced device's tokens and sync access. |
| `GET` | `/api/v1/dashboard/summary` | Yes | Returns Safe-to-Spend, net worth, monthly burn, and upcoming 7-day bills. |
| `GET/POST` | `/api/v1/accounts` | Yes (`Idempotency-Key`) | Lists accounts or creates a new account with optional encrypted PDF password rule. |
| `POST` | `/api/v1/statements/upload` | Yes (`file_sha256`) | Uploads PDF/CSV/CAS statement, triggers sandboxed decryption and parsing worker. |
| `GET` | `/api/v1/statements/{id}/review` | Yes | Returns parsed rows, confidence scores, and any running-balance diff diagnostics. |
| `POST` | `/api/v1/statements/{id}/commit` | Yes (`Idempotency-Key`) | Atomically commits reviewed statement rows to the double-entry journal. |
| `GET` | `/api/v1/transactions` | Yes | Cursor-paginated transaction query supporting date, category, account, and tax filters. |
| `PATCH` | `/api/v1/transactions/{id}` | Yes (`If-Match: version`) | Updates category, tax tag, or splits; creates balanced journal adjustment lines. |
| `POST` | `/api/v1/splits/{id}/settle` | Yes (`Idempotency-Key`) | Links an incoming UPI credit to settle an open friend reimbursement receivable. |
| `GET` | `/api/v1/wealth/portfolio` | Yes | Returns CAS investment holdings, asset allocation, net-worth history, and XIRR. |
| `GET` | `/api/v1/tax/summary/{fy}` | Yes | Generates an itemized `80C`/`80D`/`HRA`/Capital Gains deduction report for the fiscal year. |
| `POST` | `/api/v1/ai/preview-payload` | Yes | Returns the exact sanitized, bucketed JSON payload that would be sent to cloud AI. |
| `POST` | `/api/v1/ai/analyze` | Yes (`Idempotency-Key`) | Executes local Ollama or consent-signed cloud AI query and returns validated schema. |
| `POST` | `/api/v1/sync/push` | Yes (`cmd_id`) | Processes queued offline mobile commands and returns applied sequence numbers. |
| `GET` | `/api/v1/sync/pull` | Yes | Streams monotonic `server_changelog` deltas since `after_seq`. |

---

## 12. Security Model, Threat Matrix & Hardened Deployment

### 12.1 Comprehensive Threat & Mitigation Matrix

| Threat Scenario | Attack Vector / Failure Mode | Engineered Defense-in-Depth Mitigation |
| :--- | :--- | :--- |
| **Lost or Stolen Mobile Phone** | Physical extraction of phone storage. | Biometric + PIN gate; SQLCipher AES-256 database with hardware-bound key; instant remote device revocation on home server. |
| **Malicious / Crafted PDF Upload** | Buffer overflow or SSRF inside PDF parser. | Parsed inside air-gapped `finsight_pdf_worker` container (`network_mode: internal`, `read_only: true`, `cap_drop: ALL`, `no-new-privileges`). |
| **Silent Bank Statement Layout Change** | Bank swaps Debit/Credit columns in a redesign. | Layout Fingerprinter verifies header coordinates before parsing; halts import and alerts user if fingerprint drifts. |
| **Cloud AI Prompt Injection / Leakage** | Malicious merchant string attempts data exfiltration. | Raw merchant strings never enter cloud payloads; AI database user has `SELECT` only on pre-aggregated rollup views. |
| **Windows Host NVMe Drive Failure** | Complete loss of primary server SSD. | Nightly `VACUUM INTO` snapshot $\rightarrow$ Canary SQLite integrity verification $\rightarrow$ `age` X25519 encryption $\rightarrow$ `rclone` sync to offsite cloud + secondary disk. |
| **Mobile Hardware Keystore Reset** | User factory-resets phone or upgrades OS. | Authoritative database lives on home server; new phone pairs over Tailscale and pulls a fresh encrypted replica in $<15\text{ seconds}$. |

### 12.2 Windows Host `.wslconfig` & Hardened `docker-compose.yml`
Place `.wslconfig` in `C:\Users\<User>\.wslconfig` to prevent WSL2 from consuming all 16 GB of host RAM:

```ini
[wsl2]
memory=8GB
processors=6
swap=2GB
localhostForwarding=true
```

Deploy the stack with `docker-compose.yml`:

```yaml
name: finsight-production

services:
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile.api
    container_name: finsight_api
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp:size=64M,noexec,nosuid,nodev
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 512M
    volumes:
      - finsight_db:/var/lib/finsight/db:rw
      - finsight_docs:/var/lib/finsight/docs:ro
      - finsight_ipc:/var/lib/finsight/ipc:rw
    ports:
      - "${TAILSCALE_IP}:8443:8443"
    networks:
      - core_internal
      - ai_internal

  pdf_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    container_name: finsight_pdf_worker
    restart: unless-stopped
    read_only: true
    tmpfs:
      - /tmp:size=512M,noexec,nosuid,nodev
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    deploy:
      resources:
        limits:
          cpus: "3.0"
          memory: 1536M
    volumes:
      - finsight_docs:/var/lib/finsight/docs:rw
      - finsight_ipc:/var/lib/finsight/ipc:rw
    networks:
      - worker_airgap

  ollama:
    image: ollama/ollama:latest
    container_name: finsight_ollama
    restart: unless-stopped
    environment:
      - OLLAMA_KEEP_ALIVE=2m
      - OLLAMA_NUM_PARALLEL=1
      - OLLAMA_MAX_LOADED_MODELS=1
    deploy:
      resources:
        limits:
          memory: 3584M
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    volumes:
      - finsight_ollama:/root/.ollama
    networks:
      - ai_internal

  backup_worker:
    build:
      context: ./infrastructure/backup
      dockerfile: Dockerfile.backup
    container_name: finsight_backup
    restart: unless-stopped
    volumes:
      - finsight_db:/var/lib/finsight/db:ro
      - finsight_docs:/var/lib/finsight/docs:ro
      - ./infrastructure/backup/rclone.conf:/config/rclone/rclone.conf:ro
    networks:
      - backup_egress

volumes:
  finsight_db:
  finsight_docs:
  finsight_ipc:
  finsight_ollama:

networks:
  core_internal:
    internal: true
  worker_airgap:
    internal: true
  ai_internal:
    internal: true
  backup_egress:
    driver: bridge
```

---

## 13. Repository Structure, Verification Suite & 10-Week Roadmap

### 13.1 Monorepo Directory Layout

```text
finsight/
├── mobile/
│   ├── app/
│   │   ├── (auth)/
│   │   ├── (tabs)/
│   │   │   ├── index.tsx               # Safe-to-Spend & Command Center
│   │   │   ├── transactions.tsx        # FlashList & Review Diff Queue
│   │   │   ├── accounts.tsx            # Cards, Cycles & P2P Splits
│   │   │   ├── wealth.tsx              # Budgets, Recurring & CAS Portfolio
│   │   │   └── assistant.tsx           # Hybrid AI & Consent Preview
│   ├── components/
│   ├── database/
│   │   ├── schema.ts                   # Local SQLCipher Replica Schema
│   │   └── outbox.ts                   # FIFO Command Outbox Queue
│   ├── native-modules/
│   │   └── notification-listener/      # Provisional Real-Time Spend Capture
│   └── sync/
│       └── delta-sync-client.ts
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── security.py             # Argon2id, AES-256-GCM, JWT
│   │   ├── database/
│   │   │   └── session.py              # SQLCipher Connection Pool
│   │   ├── finance/
│   │   │   ├── ledger_service.py       # Double-Entry Journal Engine
│   │   │   ├── safe_to_spend.py        # Liquidity Calculator
│   │   │   ├── refund_netting.py       # Cross-Cycle Reversal Linker
│   │   │   └── xirr_engine.py          # Newton-Raphson Portfolio XIRR
│   │   ├── ingestion/
│   │   │   ├── password_vault.py       # Automated PDF Decryption
│   │   │   ├── drift_guard.py          # Layout Fingerprint Verifier
│   │   │   ├── normalizer.py           # UPI/IMPS/NEFT Regex Engine
│   │   │   ├── onnx_categorizer.py     # all-MiniLM-L6-v2 CPU Matcher
│   │   │   └── parsers/
│   │   │       ├── base_parser.py
│   │   │       ├── sbi_parser.py
│   │   │       ├── hdfc_parser.py
│   │   │       ├── icici_parser.py
│   │   │       ├── axis_parser.py
│   │   │       └── cas_parser.py       # CAMS / NSDL Portfolio Parser
│   │   ├── ai/
│   │   │   ├── router.py
│   │   │   ├── privacy_filter.py       # 500 INR Bucketer & Masker
│   │   │   ├── ollama_provider.py
│   │   │   └── cloud_providers.py
│   │   └── sync/
│   │       └── changelog_service.py
│   ├── migrations/
│   └── tests/
│       ├── test_ledger_invariants.py   # Hypothesis Property-Based Tests
│       ├── test_parsers_regression.py  # Synthetic PDF Corpus Tests
│       └── test_privacy_gateway.py
├── infrastructure/
│   ├── docker/
│   ├── backup/
│   │   └── backup_verify_sync.sh       # VACUUM INTO + Canary + Age + Rclone
│   └── scripts/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

### 13.2 10-Week Production Engineering Roadmap

| Schedule | Engineering Workstream | Concrete Deliverables & Exit Criteria |
| :--- | :--- | :--- |
| **Week 1** | **Foundation & Double-Entry Core** | Git monorepo, Docker Compose with memory caps, SQLCipher database + zero-sum triggers, Argon2id key hierarchy, and device authentication. |
| **Weeks 2–3** | **Statement Ingestion & Decryption** | Automated PDF Password Vault, Layout Drift Fingerprinter, PyMuPDF + RapidOCR worker, UPI/IMPS regex normalizer, first bank parser, and first credit card parser. |
| **Week 4** | **Reconciliation & Categorization** | Row-by-row running balance verifier, visual diff API, ONNX `all-MiniLM-L6-v2` local CPU categorizer, confidence-tiered approval queue, and monthly rollup tables. |
| **Week 5** | **Liquidity & Smart Accounting** | Safe-to-Spend calculator, own-account transfer pairing, credit card bill settlement linker, cross-cycle refund netting, and P2P split reimbursement sub-ledger. |
| **Week 6** | **Wealth, CAS & Subscriptions** | CAMS/NSDL CAS PDF parser, ISIN holdings table, Newton-Raphson XIRR engine, subscription price-creep detector, financial goals, and tax section tagging (`80C`/`80D`). |
| **Week 7** | **Mobile App & Provisional Capture** | Expo custom dev build with SQLCipher, Home Safe-to-Spend dashboard, Transactions FlashList, Review Diff screen, and Android/iOS provisional spend capture. |
| **Week 8** | **Offline-First CQRS Sync** | Mobile FIFO command outbox, server idempotency middleware, monotonic `server_changelog` cursor pull, optimistic concurrency resolution UI, and Wake-on-LAN trigger. |
| **Week 9** | **Zero-Trust AI Gateway** | Local Ollama integration (`2m` auto-eviction), Cloud Privacy Sanitizer ($\pm 500\text{ INR}$ bucketing), mobile payload preview & consent signature UI, and schema validation. |
| **Week 10** | **Hardening, Backup & Release** | Automated `VACUUM INTO` + `age` + `rclone` 3-2-1 backup worker with canary restore verification, Hypothesis property-based invariant test suite, and signed iOS/Android builds. |

### 13.3 Production Acceptance Checklist
* [ ] Encrypted Indian bank and credit card PDF statements unlock automatically via the Account Password Vault.
* [ ] Every row in a multi-page statement is verified against the running balance ($B_i = B_{i-1} + C_i - D_i$), pinpointing any OCR error to the exact line.
* [ ] All journal lines across the entire database sum strictly to `0` (`SELECT TOTAL(signed_amount_minor) FROM journal_lines` $= 0$).
* [ ] Credit card bill payments and own-account transfers never inflate monthly income or expense totals.
* [ ] Group dining splits route friend shares into `Pending_Reimbursements`, and incoming friend UPI repayments settle the receivable without distorting income.
* [ ] Dashboard displays real-time **Safe-to-Spend** liquidity after subtracting card liabilities, 30-day obligations, and goal locks.
* [ ] CAMS/NSDL CAS PDF import updates mutual fund/equity valuations and computes portfolio XIRR offline.
* [ ] Provisional mobile notification spends merge seamlessly into authoritative statement rows upon monthly PDF upload without creating duplicates.
* [ ] Host PC RAM usage inside WSL2 stays below $2.5\text{ GB}$ during normal operation, and Ollama unloads from the GTX 1050 Ti VRAM within 2 minutes of inactivity.
* [ ] Zero outbound network packets leave the server toward cloud AI providers unless the user explicitly signs the bucketed preview payload on their mobile device.
* [ ] Nightly encrypted backups pass automated canary restore and zero-sum ledger verification before syncing offsite.

---

## 14. Technical References & Standards
* **Expo SQLite & SQLCipher Native Configuration:** `https://docs.expo.dev/versions/latest/sdk/sqlite/`
* **FastAPI Production Deployment & Security:** `https://fastapi.tiangolo.com/`
* **SQLAlchemy 2.0 & Alembic Migrations:** `https://docs.sqlalchemy.org/` | `https://alembic.sqlalchemy.org/`
* **PyMuPDF (`fitz`) Document & Encryption API:** `https://pymupdf.readthedocs.io/`
* **RapidOCR ONNX Runtime Documentation:** `https://rapidai.github.io/RapidOCRDocs/`
* **Ollama GPU & Memory Management:** `https://docs.ollama.com/gpu`
* **Tailscale WireGuard Mesh & Wake-on-LAN:** `https://tailscale.com/kb/`
* **Age File Encryption Specification:** `https://age-encryption.org/v1`