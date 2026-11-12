import pytest

from app.ingestion.drift_guard import (
    LayoutDriftError,
    compute_layout_fingerprint,
    verify_layout,
)

HEADERS = ["date", "description", "debit", "credit", "balance"]


def test_fingerprint_is_64_hex_characters_and_deterministic():
    # Arrange / Act
    first = compute_layout_fingerprint(HEADERS, None)
    second = compute_layout_fingerprint(HEADERS, None)

    # Assert
    assert first == second
    assert len(first) == 64
    assert all(char in "0123456789abcdef" for char in first)


def test_same_headers_with_different_case_and_spacing_give_same_fingerprint():
    # Arrange
    spaced = ["  DATE ", "Description", "debit", "CREDIT", "Balance  "]

    # Act / Assert
    assert compute_layout_fingerprint(spaced, None) == compute_layout_fingerprint(HEADERS, None)


def test_internal_whitespace_runs_are_collapsed_in_headers():
    # Arrange
    headers = ["txn   date", "running\tbalance"]

    # Act / Assert
    assert compute_layout_fingerprint(headers, None) == compute_layout_fingerprint(
        ["txn date", "running balance"], None
    )


def test_reordered_headers_give_different_fingerprint():
    # Arrange
    reordered = ["description", "date", "debit", "credit", "balance"]

    # Act / Assert
    assert compute_layout_fingerprint(reordered, None) != compute_layout_fingerprint(HEADERS, None)


def test_different_header_names_give_different_fingerprint():
    # Arrange
    renamed = ["date", "narration", "debit", "credit", "balance"]

    # Act / Assert
    assert compute_layout_fingerprint(renamed, None) != compute_layout_fingerprint(HEADERS, None)


def test_span_jitter_within_rounding_is_stable():
    # Arrange: both sets round to (100, 200) and (300, 400) at the 5-unit grid
    spans = [(100, 200), (300, 400)]
    jittered = [(101, 199), (302, 398)]

    # Act / Assert
    assert compute_layout_fingerprint(HEADERS, spans) == compute_layout_fingerprint(HEADERS, jittered)


def test_span_change_beyond_rounding_changes_fingerprint():
    # Arrange
    spans = [(100, 200)]
    moved = [(100, 210)]

    # Act / Assert
    assert compute_layout_fingerprint(HEADERS, spans) != compute_layout_fingerprint(HEADERS, moved)


def test_presence_of_spans_changes_fingerprint():
    # Arrange
    spans = [(100, 200)]

    # Act / Assert
    assert compute_layout_fingerprint(HEADERS, spans) != compute_layout_fingerprint(HEADERS, None)


def test_verify_layout_is_noop_when_no_known_fingerprint():
    # Arrange
    computed = compute_layout_fingerprint(HEADERS, None)

    # Act / Assert
    assert verify_layout(None, computed) is None


def test_verify_layout_passes_when_fingerprints_match():
    # Arrange
    computed = compute_layout_fingerprint(HEADERS, None)

    # Act / Assert
    assert verify_layout(computed, computed) is None


def test_verify_layout_raises_layout_drift_on_mismatch():
    # Arrange
    known = compute_layout_fingerprint(HEADERS, None)
    drifted = compute_layout_fingerprint(["date", "narration", "debit", "credit", "balance"], None)

    # Act / Assert
    with pytest.raises(LayoutDriftError, match="LAYOUT_DRIFT"):
        verify_layout(known, drifted)
