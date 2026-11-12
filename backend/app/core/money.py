"""Integer-only money helpers. Amounts are paise (minor units); floats are rejected."""

import re
from decimal import Decimal, InvalidOperation

_MINOR_PER_MAJOR = 100


def _reject_float(value: object) -> None:
    if isinstance(value, float):
        raise TypeError("Floats are not allowed for monetary values")


_MAX_MINOR = 2**63 - 1
_AMOUNT_RE = re.compile(r"-?\d+(\.\d{1,2})?")


def to_minor(amount: str | Decimal | int) -> int:
    """Convert rupees to paise.

    Strings must look like "-?digits[.1-2 digits]" (surrounding whitespace is stripped). Raises
    ValueError for malformed input, more than 2 decimal places, or a result outside +-(2**63 - 1).
    """
    _reject_float(amount)
    if isinstance(amount, bool) or not isinstance(amount, str | Decimal | int):
        raise TypeError("amount must be str, Decimal or int")
    if isinstance(amount, str):
        text = amount.strip()
        if not _AMOUNT_RE.fullmatch(text):
            raise ValueError(f"Invalid monetary amount: {amount!r}")
        amount = text
    try:
        value = Decimal(amount)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid monetary amount: {amount!r}") from exc
    if not value.is_finite():
        raise ValueError(f"Invalid monetary amount: {amount!r}")
    try:
        minor = value * _MINOR_PER_MAJOR
    except ArithmeticError as exc:
        raise ValueError(f"Invalid monetary amount: {amount!r}") from exc
    if minor != minor.to_integral_value():
        raise ValueError("Amount has more than 2 decimal places")
    result = int(minor)
    if abs(result) > _MAX_MINOR:
        raise ValueError("Amount is outside the 64-bit range")
    return result


def format_minor(amount_minor: int) -> str:
    """Format paise as a rupee string, e.g. -150050 -> '-1500.50'."""
    _reject_float(amount_minor)
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        raise TypeError("amount_minor must be int")
    sign = "-" if amount_minor < 0 else ""
    major, minor = divmod(abs(amount_minor), _MINOR_PER_MAJOR)
    return f"{sign}{major}.{minor:02d}"


def round_half_up_to_bucket(amount_minor: int, bucket_minor: int) -> int:
    """Round to the nearest multiple of bucket_minor; ties go away from zero (symmetric)."""
    _reject_float(amount_minor)
    _reject_float(bucket_minor)
    if bucket_minor <= 0:
        raise ValueError("bucket_minor must be positive")
    magnitude = abs(amount_minor)
    rounded = ((2 * magnitude + bucket_minor) // (2 * bucket_minor)) * bucket_minor
    return -rounded if amount_minor < 0 else rounded
