from datetime import date

import pytest

from app.ingestion.normalizer import (
    IndianBankingNormalizer,
    NormalizationResult,
    RawParsedRow,
)

ACCOUNT_ID = "acct-1"
OPENING_BALANCE = 100_000
TX_DATE = date(2026, 3, 14)


def _row(
    row_index: int,
    description: str,
    *,
    debit: int = 0,
    credit: int = 0,
    stated: int | None = None,
    tx_date: date = TX_DATE,
) -> RawParsedRow:
    return RawParsedRow(
        row_index=row_index,
        page_number=1,
        tx_date=tx_date,
        raw_description=description,
        debit_minor=debit,
        credit_minor=credit,
        stated_running_balance_minor=stated,
    )


def _normalize(rows: list[RawParsedRow], closing: int = 0) -> NormalizationResult:
    return IndianBankingNormalizer.normalize_and_verify_rows(ACCOUNT_ID, OPENING_BALANCE, closing, rows)


def test_upi_pattern_one_extracts_utr_vpa_and_clean_merchant():
    # Arrange
    narration = "UPI/DR/412345678901/ZOMATO LTD/UTIB/Zomato.Pay@icici"
    rows = [_row(0, narration, debit=25_000)]

    # Act
    candidate = _normalize(rows).candidates[0]

    # Assert
    assert candidate.channel == "UPI"
    assert candidate.external_utr == "412345678901"
    assert candidate.extracted_vpa == "zomato.pay@icici"
    assert candidate.clean_description == "ZOMATO"
    assert candidate.raw_description == narration


def test_upi_pattern_two_extracts_vpa_before_utr():
    # Arrange
    narration = "UPI/RAHUL KUMAR/rahul.k@okaxis/OKAXIS/412345678902"
    rows = [_row(0, narration, credit=50_000)]

    # Act
    candidate = _normalize(rows).candidates[0]

    # Assert
    assert candidate.channel == "UPI"
    assert candidate.external_utr == "412345678902"
    assert candidate.extracted_vpa == "rahul.k@okaxis"
    assert candidate.clean_description == "RAHUL KUMAR"
    assert candidate.direction == "CREDIT"


def test_imps_narration_is_classified_with_utr_and_no_vpa():
    # Arrange
    rows = [_row(0, "IMPS/P2A/412345678903/JOHN DOE/HDFC", debit=10_000)]

    # Act
    candidate = _normalize(rows).candidates[0]

    # Assert
    assert candidate.channel == "IMPS"
    assert candidate.external_utr == "412345678903"
    assert candidate.extracted_vpa is None
    assert candidate.clean_description == "JOHN DOE"


def test_neft_narration_strips_corporate_noise_from_merchant():
    # Arrange
    rows = [_row(0, "NEFT/HDFCN52024010112345678/ACME TRADERS PVT LTD", credit=900_000)]

    # Act
    candidate = _normalize(rows).candidates[0]

    # Assert
    assert candidate.channel == "NEFT"
    assert candidate.external_utr == "HDFCN52024010112345678"
    assert candidate.clean_description == "ACME TRADERS"


def test_rtgs_narration_keeps_rtgs_channel():
    # Arrange
    rows = [_row(0, "RTGS-SBIN52024011512345678-LARSEN AND TOUBRO", debit=500_000)]

    # Act
    candidate = _normalize(rows).candidates[0]

    # Assert
    assert candidate.channel == "RTGS"
    assert candidate.external_utr == "SBIN52024011512345678"
    assert candidate.clean_description == "LARSEN AND TOUBRO"


def test_unmatched_narration_falls_back_to_other_channel_with_cleaned_text():
    # Arrange
    rows = [_row(0, "  ATM WDL 1234   MUMBAI ", debit=200_000)]

    # Act
    candidate = _normalize(rows).candidates[0]

    # Assert
    assert candidate.channel == "OTHER"
    assert candidate.external_utr is None
    assert candidate.extracted_vpa is None
    assert candidate.raw_description == "ATM WDL 1234 MUMBAI"
    assert candidate.clean_description == "ATM WDL 1234"


def test_balanced_rows_produce_no_mismatches():
    # Arrange
    rows = [
        _row(0, "UPI/DR/412345678901/SHOP/shop@ybl", debit=20_000, stated=80_000),
        _row(1, "IMPS/P2A/412345678902/SALARY/HDFC", credit=50_000, stated=130_000),
    ]

    # Act
    result = _normalize(rows, closing=130_000)

    # Assert
    assert result.mismatches == ()
    assert all(candidate.balance_verified for candidate in result.candidates)
    assert result.final_computed_balance_minor == 130_000


def test_single_mismatch_is_flagged_only_at_its_row_after_reanchoring():
    # Arrange: row 1 states 125_000 but the computed balance is 130_000.
    rows = [
        _row(0, "IMPS/P2A/412345678901/ALPHA", credit=50_000, stated=150_000),
        _row(1, "IMPS/P2A/412345678902/BETA", debit=20_000, stated=125_000),
        _row(2, "IMPS/P2A/412345678903/GAMMA", debit=5_000, stated=120_000),
    ]

    # Act
    result = _normalize(rows, closing=120_000)

    # Assert
    assert len(result.mismatches) == 1
    mismatch = result.mismatches[0]
    assert mismatch.row_index == 1
    assert mismatch.expected_minor == 130_000
    assert mismatch.stated_minor == 125_000
    assert [c.balance_verified for c in result.candidates] == [True, False, True]
    assert result.final_computed_balance_minor == 120_000


def test_rows_with_no_stated_balance_are_never_flagged():
    # Arrange
    rows = [
        _row(0, "ATM WDL 1", debit=10_000),
        _row(1, "ATM WDL 2", credit=4_000),
    ]

    # Act
    result = _normalize(rows, closing=94_000)

    # Assert
    assert result.mismatches == ()
    assert all(candidate.balance_verified for candidate in result.candidates)
    assert result.final_computed_balance_minor == 94_000


def test_closing_balance_matches_when_final_computed_equals_closing():
    # Arrange
    rows = [_row(0, "ATM WDL 1", debit=10_000)]

    # Act
    result = _normalize(rows, closing=90_000)

    # Assert
    assert result.closing_balance_matches is True


def test_closing_balance_mismatch_is_reported():
    # Arrange
    rows = [_row(0, "ATM WDL 1", debit=10_000)]

    # Act
    result = _normalize(rows, closing=91_000)

    # Assert
    assert result.closing_balance_matches is False
    assert result.final_computed_balance_minor == 90_000


def test_same_utr_produces_same_fingerprint_regardless_of_date():
    # Arrange
    rows = [
        _row(0, "UPI/DR/412345678901/SHOP/shop@ybl", debit=20_000),
        _row(1, "UPI/DR/412345678901/SHOP/shop@ybl", debit=20_000, tx_date=date(2026, 3, 15)),
    ]

    # Act
    candidates = _normalize(rows).candidates

    # Assert
    assert candidates[0].dedup_fingerprint == candidates[1].dedup_fingerprint


def test_identical_non_utr_rows_on_same_day_get_different_fingerprints():
    # Arrange
    rows = [
        _row(0, "ATM WDL 1234 MUMBAI", debit=50_000),
        _row(1, "ATM WDL 1234 MUMBAI", debit=50_000),
    ]

    # Act
    candidates = _normalize(rows).candidates

    # Assert
    assert candidates[0].dedup_fingerprint != candidates[1].dedup_fingerprint


def test_fingerprints_are_deterministic_across_repeated_calls():
    # Arrange
    rows = [
        _row(0, "ATM WDL 1234 MUMBAI", debit=50_000),
        _row(1, "ATM WDL 1234 MUMBAI", debit=50_000),
        _row(2, "UPI/DR/412345678901/SHOP/shop@ybl", debit=20_000),
    ]

    # Act
    first = [c.dedup_fingerprint for c in _normalize(rows).candidates]
    second = [c.dedup_fingerprint for c in _normalize(rows).candidates]

    # Assert
    assert first == second


def test_zero_amount_row_raises_value_error_naming_row_index():
    # Arrange
    rows = [_row(3, "ATM WDL", debit=0, credit=0)]

    # Act / Assert
    with pytest.raises(ValueError, match="row_index=3"):
        _normalize(rows)


def test_row_with_both_debit_and_credit_raises_value_error():
    # Arrange
    rows = [_row(2, "ATM WDL", debit=100, credit=100)]

    # Act / Assert
    with pytest.raises(ValueError, match="row_index=2"):
        _normalize(rows)


def test_negative_amount_raises_value_error_naming_row_index():
    # Arrange
    rows = [_row(4, "ATM WDL", debit=-100)]

    # Act / Assert
    with pytest.raises(ValueError, match="row_index=4"):
        _normalize(rows)


def test_float_amount_raises_type_error():
    # Arrange
    rows = [_row(0, "ATM WDL", debit=100.5)]  # type: ignore[arg-type]

    # Act / Assert
    with pytest.raises(TypeError, match="row_index=0"):
        _normalize(rows)


def test_bool_amount_raises_type_error():
    # Arrange
    rows = [_row(0, "ATM WDL", credit=True)]  # type: ignore[arg-type]

    # Act / Assert
    with pytest.raises(TypeError, match="row_index=0"):
        _normalize(rows)
