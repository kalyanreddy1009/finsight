"""Zero-trust privacy gateway: sanitizes financial context before any cloud AI call."""

import hashlib
import json
from typing import Annotated, Any

from pydantic import BaseModel, Field

from app.core.money import round_half_up_to_bucket

REDACTED_CATEGORY_NAME = "Redacted_Private"


DEFAULT_DISCLAIMER = "Advisory insight only; verified against local deterministic ledger."
HEADLINE_MAX_CHARS = 160
ITEM_MAX_CHARS = 300
MAX_OBSERVATIONS = 5
MAX_ACTIONS = 4

InsightLine = Annotated[str, Field(max_length=ITEM_MAX_CHARS)]


class AIInsightResponseSchema(BaseModel):
    summary_headline: str = Field(..., max_length=HEADLINE_MAX_CHARS)
    key_observations: list[InsightLine] = Field(..., max_length=MAX_OBSERVATIONS)
    recommended_actions: list[InsightLine] = Field(..., max_length=MAX_ACTIONS)
    disclaimer: str = Field(default=DEFAULT_DISCLAIMER)


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
        bucketed_minor = round_half_up_to_bucket(amount_minor, cls.BUCKET_PAISE)
        return bucketed_minor // 100

    @staticmethod
    def _normalize_category_name(name: str) -> str:
        return name.strip().casefold()

    @classmethod
    def build_cloud_safe_payload(
        cls,
        year_month: str,
        income_minor: int,
        category_spend_minor: dict[str, int],
        sensitive_categories: set[str],
    ) -> tuple[dict[str, Any], str]:
        safe_categories: dict[str, int] = {}
        redacted_sum_minor = 0
        normalized_sensitive = {cls._normalize_category_name(name) for name in sensitive_categories}
        normalized_redacted = cls._normalize_category_name(REDACTED_CATEGORY_NAME)

        for cat_name, spend_minor in category_spend_minor.items():
            normalized_name = cls._normalize_category_name(cat_name)
            if normalized_name in normalized_sensitive or normalized_name == normalized_redacted:
                redacted_sum_minor += spend_minor
            else:
                safe_categories[cat_name] = cls._round_to_bucket_inr(spend_minor)

        redacted_bucket_inr = cls._round_to_bucket_inr(redacted_sum_minor)
        if redacted_bucket_inr != 0:
            safe_categories[REDACTED_CATEGORY_NAME] = redacted_bucket_inr

        payload = {
            "period": year_month,
            "currency": "INR",
            "bucket_resolution_inr": 500,
            "approximate_monthly_income_inr": cls._round_to_bucket_inr(income_minor),
            "category_expenses_inr": safe_categories,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
        return payload, payload_hash
