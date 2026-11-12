"""Deterministic bank-narration normalizer and running-balance verifier.

Pure logic: no database access and no PDF library imports.
"""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

CLEAN_DESCRIPTION_KEY_LENGTH = 24
FALLBACK_DESCRIPTION_LENGTH = 32


@dataclass(frozen=True)
class RawParsedRow:
    row_index: int
    page_number: int
    tx_date: date
    raw_description: str
    debit_minor: int
    credit_minor: int
    stated_running_balance_minor: int | None


@dataclass(frozen=True)
class NormalizedTransactionCandidate:
    row_index: int
    tx_date: date
    raw_description: str
    clean_description: str
    channel: str
    extracted_vpa: str | None
    external_utr: str | None
    amount_minor: int
    direction: str  # 'DEBIT' or 'CREDIT'
    dedup_fingerprint: str
    balance_verified: bool


@dataclass(frozen=True)
class BalanceMismatch:
    row_index: int
    expected_minor: int
    stated_minor: int


@dataclass(frozen=True)
class NormalizationResult:
    candidates: tuple[NormalizedTransactionCandidate, ...]
    final_computed_balance_minor: int
    mismatches: tuple[BalanceMismatch, ...]
    closing_balance_matches: bool


def _validate_amounts(row: RawParsedRow) -> None:
    for field_name, amount in (("debit_minor", row.debit_minor), ("credit_minor", row.credit_minor)):
        if isinstance(amount, bool) or not isinstance(amount, int):
            type_name = type(amount).__name__
            raise TypeError(f"row_index={row.row_index}: {field_name} must be int, not {type_name}")
        if amount < 0:
            raise ValueError(f"row_index={row.row_index}: {field_name} must not be negative")
    if (row.debit_minor > 0) == (row.credit_minor > 0):
        raise ValueError(f"row_index={row.row_index}: exactly one of debit_minor or credit_minor must be > 0")


def _apply_running_balance(running_balance: int, row: RawParsedRow) -> tuple[int, BalanceMismatch | None]:
    computed = running_balance + row.credit_minor - row.debit_minor
    stated = row.stated_running_balance_minor
    if stated is None or computed == stated:
        return computed, None
    # Re-anchor to the stated balance so a single row error doesn't cascade false positives.
    return stated, BalanceMismatch(row_index=row.row_index, expected_minor=computed, stated_minor=stated)


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
        raw_rows: list[RawParsedRow],
    ) -> NormalizationResult:
        """Normalizes rows and performs row-by-row running balance verification."""
        running_balance = opening_balance_minor
        candidates: list[NormalizedTransactionCandidate] = []
        mismatches: list[BalanceMismatch] = []
        base_seed_counts: Counter[str] = Counter()

        for row in raw_rows:
            _validate_amounts(row)
            running_balance, mismatch = _apply_running_balance(running_balance, row)
            if mismatch is not None:
                mismatches.append(mismatch)
            candidates.append(cls._build_candidate(account_id, row, mismatch is None, base_seed_counts))

        return NormalizationResult(
            candidates=tuple(candidates),
            final_computed_balance_minor=running_balance,
            mismatches=tuple(mismatches),
            closing_balance_matches=running_balance == closing_balance_minor,
        )

    @classmethod
    def _build_candidate(
        cls,
        account_id: str,
        row: RawParsedRow,
        balance_verified: bool,
        base_seed_counts: Counter[str],
    ) -> NormalizedTransactionCandidate:
        direction = "DEBIT" if row.debit_minor > 0 else "CREDIT"
        amount_minor = row.debit_minor if row.debit_minor > 0 else row.credit_minor
        collapsed = " ".join(row.raw_description.strip().split())
        channel, vpa, utr, merchant_raw = cls._extract_channel(collapsed)
        cleaned = cls._clean_description(merchant_raw, collapsed)
        base_seed = cls._fingerprint_seed(account_id, row.tx_date, direction, amount_minor, utr, cleaned)
        return NormalizedTransactionCandidate(
            row_index=row.row_index,
            tx_date=row.tx_date,
            raw_description=collapsed,
            clean_description=cleaned,
            channel=channel,
            extracted_vpa=vpa,
            external_utr=utr,
            amount_minor=amount_minor,
            direction=direction,
            dedup_fingerprint=cls._dedup_fingerprint(base_seed, utr, base_seed_counts),
            balance_verified=balance_verified,
        )

    @classmethod
    def _extract_channel(cls, collapsed: str) -> tuple[str, str | None, str | None, str]:
        """Returns (channel, vpa, utr, merchant_raw) for a whitespace-collapsed narration."""
        for upi_re in cls.UPI_PATTERNS:
            m = upi_re.search(collapsed)
            if m:
                return "UPI", m.group("vpa").lower(), m.group("utr"), m.group("merchant")

        m_imps = cls.IMPS_PATTERN.search(collapsed)
        if m_imps:
            return "IMPS", None, m_imps.group("utr"), m_imps.group("merchant")

        m_neft = cls.NEFT_PATTERN.search(collapsed)
        if m_neft:
            return m_neft.group("channel").upper(), None, m_neft.group("utr"), m_neft.group("merchant")

        return "OTHER", None, None, collapsed

    @classmethod
    def _clean_description(cls, merchant_raw: str, collapsed: str) -> str:
        cleaned = cls.CORP_NOISE.sub("", merchant_raw)
        cleaned = re.sub(r"[^a-zA-Z0-9\s&]", " ", cleaned)
        return " ".join(cleaned.upper().split()) or collapsed[:FALLBACK_DESCRIPTION_LENGTH].upper()

    @staticmethod
    def _fingerprint_seed(
        account_id: str,
        tx_date: date,
        direction: str,
        amount_minor: int,
        utr: str | None,
        cleaned: str,
    ) -> str:
        if utr:
            return f"{account_id}|{direction}|{amount_minor}|UTR:{utr}"
        return (
            f"{account_id}|{tx_date.isoformat()}|{direction}|{amount_minor}"
            f"|{cleaned[:CLEAN_DESCRIPTION_KEY_LENGTH]}"
        )

    @staticmethod
    def _dedup_fingerprint(base_seed: str, utr: str | None, base_seed_counts: Counter[str]) -> str:
        if utr:
            seed = base_seed
        else:
            # Genuinely separate identical purchases on one day share a base seed; the occurrence
            # index keeps their fingerprints distinct while staying deterministic per call.
            seed = f"{base_seed}|{base_seed_counts[base_seed]}"
            base_seed_counts[base_seed] += 1
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()
