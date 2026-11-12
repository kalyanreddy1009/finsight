"""Layout fingerprints for statement tables, and a guard that flags layout drift.

A fingerprint is a SHA-256 over the normalised header names (in file order) and, when supplied,
the column spans rounded to SPAN_ROUNDING_UNITS so that sub-pixel jitter does not change it.
"""

import hashlib
import json
from collections.abc import Sequence

SPAN_ROUNDING_UNITS = 5


class LayoutDriftError(Exception):
    """Raised when a statement's layout differs from the layout known for its source."""


def normalise_header_name(name: str) -> str:
    """Lower-cases a header and collapses runs of whitespace to single spaces."""
    return " ".join(name.split()).lower()


def _round_span(value: int) -> int:
    half_unit = SPAN_ROUNDING_UNITS // 2
    return (value + half_unit) // SPAN_ROUNDING_UNITS * SPAN_ROUNDING_UNITS


def compute_layout_fingerprint(
    headers: Sequence[str],
    column_spans: Sequence[tuple[int, int]] | None,
) -> str:
    """Returns a deterministic SHA-256 hex digest describing a statement table layout."""
    payload = {
        "headers": [normalise_header_name(header) for header in headers],
        "spans": None
        if column_spans is None
        else [[_round_span(start), _round_span(end)] for start, end in column_spans],
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_layout(known_fingerprint: str | None, computed_fingerprint: str) -> None:
    """Raises LayoutDriftError when a known layout differs from the computed one.

    A None known fingerprint means this is the first statement for the source, so there is nothing
    to compare against.
    """
    if known_fingerprint is None:
        return
    if known_fingerprint != computed_fingerprint:
        raise LayoutDriftError(
            "LAYOUT_DRIFT: statement layout differs from the known layout for this source "
            f"(expected {known_fingerprint[:12]}, got {computed_fingerprint[:12]})"
        )
