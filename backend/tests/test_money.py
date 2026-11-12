from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.money import format_minor, round_half_up_to_bucket, to_minor


@pytest.mark.parametrize(
    ("amount", "expected"),
    [("1500.50", 150050), ("0.01", 1), ("-12.3", -1230), (Decimal("7.25"), 725), (3, 300), ("10", 1000)],
)
def test_to_minor_converts_rupees_to_paise(amount, expected):
    assert to_minor(amount) == expected


def test_to_minor_rejects_more_than_two_decimal_places():
    with pytest.raises(ValueError):
        to_minor("1.001")


def test_to_minor_rejects_invalid_string():
    with pytest.raises(ValueError):
        to_minor("abc")


def test_to_minor_rejects_float():
    with pytest.raises(TypeError):
        to_minor(1.5)


@pytest.mark.parametrize(
    ("minor", "expected"),
    [(-150050, "-1500.50"), (150050, "1500.50"), (5, "0.05"), (0, "0.00"), (-5, "-0.05")],
)
def test_format_minor_renders_rupees(minor, expected):
    assert format_minor(minor) == expected


def test_format_minor_rejects_float():
    with pytest.raises(TypeError):
        format_minor(1.0)


@pytest.mark.parametrize(
    ("amount", "bucket", "expected"),
    [
        (149, 100, 100),
        (150, 100, 200),
        (151, 100, 200),
        (-149, 100, -100),
        (-150, 100, -200),
        (-151, 100, -200),
        (0, 100, 0),
        (49, 100, 0),
        (-49, 100, 0),
        (25, 50, 50),
        (-25, 50, -50),
    ],
)
def test_round_half_up_to_bucket_is_symmetric_and_ties_away_from_zero(amount, bucket, expected):
    assert round_half_up_to_bucket(amount, bucket) == expected


def test_round_half_up_to_bucket_rejects_float():
    with pytest.raises(TypeError):
        round_half_up_to_bucket(1.5, 100)


def test_round_half_up_to_bucket_rejects_non_positive_bucket():
    with pytest.raises(ValueError):
        round_half_up_to_bucket(10, 0)


@given(st.integers(min_value=-(10**12), max_value=10**12))
def test_format_then_parse_round_trips(minor):
    assert to_minor(format_minor(minor)) == minor


@pytest.mark.parametrize("bad", ["1e2", "1_0", "", "  ", "NaN", "Infinity", "1.", ".5", "--1", "1,000"])
def test_to_minor_rejects_malformed_strings(bad):
    with pytest.raises(ValueError):
        to_minor(bad)


def test_to_minor_strips_surrounding_whitespace():
    assert to_minor(" 12.5 ") == 1250


@pytest.mark.parametrize("big", ["92233720368547758.08", 2**63, -(2**63), Decimal("1" + "0" * 30)])
def test_to_minor_rejects_overflow(big):
    with pytest.raises(ValueError):
        to_minor(big)


def test_to_minor_accepts_largest_representable_amount():
    assert to_minor("92233720368547758.07") == 2**63 - 1


def test_to_minor_rejects_decimal_exponent_overflow_with_value_error():
    with pytest.raises(ValueError):
        to_minor(Decimal("1E+999999999"))
