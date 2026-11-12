import json

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from app.ai.privacy_filter import AIInsightResponseSchema, ZeroTrustPrivacyGateway

EXPECTED_TOP_LEVEL_KEYS = {
    "period",
    "currency",
    "bucket_resolution_inr",
    "approximate_monthly_income_inr",
    "category_expenses_inr",
}


@pytest.mark.parametrize(
    ("amount_minor", "expected_inr"),
    [
        (0, 0),
        (24_999, 0),
        (25_000, 500),
        (124_999, 1000),
        (125_000, 1500),
        (127_500, 1500),
        (-25_000, -500),
    ],
)
def test_amounts_round_half_up_to_nearest_500_inr(amount_minor, expected_inr):
    # Arrange / Act
    result = ZeroTrustPrivacyGateway._round_to_bucket_inr(amount_minor)

    # Assert
    assert result == expected_inr


def test_sensitive_categories_are_summed_into_redacted_bucket_and_names_absent():
    # Arrange
    spend = {"Groceries": 10_000_00, "Therapy": 12_000_00, "Clinic": 3_000_00}

    # Act
    payload, _ = ZeroTrustPrivacyGateway.build_cloud_safe_payload(
        "2026-10", 80_000_00, spend, {"Therapy", "Clinic"}
    )
    serialized = json.dumps(payload)

    # Assert
    assert payload["category_expenses_inr"] == {"Groceries": 10_000, "Redacted_Private": 15_000}
    assert "Therapy" not in serialized
    assert "Clinic" not in serialized


def test_input_category_named_redacted_private_is_folded_into_redacted_bucket():
    # Arrange
    spend = {"Redacted_Private": 5_000_00, "Rent": 20_000_00}

    # Act
    payload, _ = ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", 0, spend, set())

    # Assert
    assert payload["category_expenses_inr"] == {"Rent": 20_000, "Redacted_Private": 5_000}


def test_payload_has_exactly_the_five_spec_top_level_keys():
    # Arrange / Act
    payload, _ = ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", 1_00_000_00, {}, set())

    # Assert
    assert set(payload) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["currency"] == "INR"
    assert payload["bucket_resolution_inr"] == 500


def test_hash_is_stable_across_dict_insertion_order():
    # Arrange
    first = {"Food": 4_000_00, "Fuel": 2_000_00}
    second = {"Fuel": 2_000_00, "Food": 4_000_00}

    # Act
    _, hash_first = ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", 50_000_00, first, set())
    _, hash_second = ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", 50_000_00, second, set())

    # Assert
    assert hash_first == hash_second


def test_hash_changes_when_a_bucketed_value_changes():
    # Arrange
    spend = {"Food": 4_000_00}

    # Act
    _, original = ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", 50_000_00, spend, set())
    _, changed = ZeroTrustPrivacyGateway.build_cloud_safe_payload(
        "2026-10", 50_000_00, {"Food": 4_500_00}, set()
    )

    # Assert
    assert original != changed


def test_hash_is_sha256_of_compact_sorted_json():
    import hashlib

    # Arrange / Act
    payload, payload_hash = ZeroTrustPrivacyGateway.build_cloud_safe_payload(
        "2026-10", 50_000_00, {"Food": 4_000_00}, set()
    )
    expected_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    # Assert
    assert payload_hash == hashlib.sha256(expected_json.encode("utf-8")).hexdigest()


@given(
    income=st.integers(min_value=0, max_value=10**10),
    spend=st.dictionaries(
        st.sampled_from(["Food", "Fuel", "Rent", "Therapy", "Redacted_Private"]),
        st.integers(min_value=0, max_value=10**10),
    ),
    sensitive=st.sets(st.sampled_from(["Food", "Fuel", "Rent", "Therapy"])),
)
def test_every_numeric_value_in_payload_is_int_multiple_of_500(income, spend, sensitive):
    # Arrange / Act
    payload, _ = ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", income, spend, sensitive)
    numbers = [payload["bucket_resolution_inr"], payload["approximate_monthly_income_inr"]]
    numbers.extend(payload["category_expenses_inr"].values())

    # Assert
    for value in numbers:
        assert type(value) is int
        assert value % 500 == 0


def test_float_spend_is_rejected():
    with pytest.raises(TypeError):
        ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", 50_000_00, {"Food": 100.5}, set())


def test_response_schema_rejects_more_than_five_observations():
    with pytest.raises(ValidationError):
        AIInsightResponseSchema(
            summary_headline="ok",
            key_observations=["a", "b", "c", "d", "e", "f"],
            recommended_actions=[],
        )


def test_response_schema_rejects_more_than_four_actions():
    with pytest.raises(ValidationError):
        AIInsightResponseSchema(
            summary_headline="ok",
            key_observations=[],
            recommended_actions=["a", "b", "c", "d", "e"],
        )


def test_response_schema_rejects_headline_longer_than_160_chars():
    with pytest.raises(ValidationError):
        AIInsightResponseSchema(
            summary_headline="x" * 161,
            key_observations=[],
            recommended_actions=[],
        )


def test_response_schema_accepts_headline_of_exactly_160_chars():
    schema = AIInsightResponseSchema(
        summary_headline="x" * 160, key_observations=["a"], recommended_actions=["b"]
    )

    assert len(schema.summary_headline) == 160


@pytest.mark.parametrize("sensitive_name", ["Health", "health ", " HEALTH"])
def test_sensitive_match_ignores_case_and_surrounding_whitespace(sensitive_name):
    # Arrange
    spend = {"health ": 7_000_00, "Food": 1_000_00}

    # Act
    payload, _ = ZeroTrustPrivacyGateway.build_cloud_safe_payload(
        "2026-10", 50_000_00, spend, {sensitive_name}
    )
    serialized = json.dumps(payload)

    # Assert
    assert payload["category_expenses_inr"] == {"Food": 1_000, "Redacted_Private": 7_000}
    assert "health" not in serialized.lower()


def test_reserved_name_check_ignores_case_and_whitespace():
    # Arrange
    spend = {" redacted_PRIVATE ": 5_000_00}

    # Act
    payload, _ = ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", 0, spend, set())

    # Assert
    assert payload["category_expenses_inr"] == {"Redacted_Private": 5_000}
    assert "redacted_PRIVATE" not in json.dumps(payload)


def test_redacted_bucket_omitted_when_sensitive_total_rounds_to_zero():
    # Arrange
    spend = {"Therapy": 200_00, "Food": 4_000_00}

    # Act
    payload, _ = ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", 50_000_00, spend, {"Therapy"})

    # Assert
    assert payload["category_expenses_inr"] == {"Food": 4_000}
    assert "Redacted_Private" not in json.dumps(payload)


def test_non_sensitive_category_rounding_to_zero_stays_in_payload():
    # Arrange
    spend = {"Snacks": 100_00}

    # Act
    payload, _ = ZeroTrustPrivacyGateway.build_cloud_safe_payload("2026-10", 0, spend, set())

    # Assert
    assert payload["category_expenses_inr"] == {"Snacks": 0}
