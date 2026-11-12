import pytest

from app.database import seed
from app.finance import chart
from app.ingestion.rule_categorizer import categorize
from tests.ingestion_fakes import add_merchant


@pytest.fixture
def food(conn):
    return chart.create_category(conn, name="Food", category_type="EXPENSE")[0]


def run(conn, text="SOMETHING", vpa=None, direction="DEBIT"):
    return categorize(conn, clean_description=text, extracted_vpa=vpa, direction=direction)


def test_vpa_match_is_case_insensitive_and_scores_099(conn, food):
    merchant = add_merchant(conn, "Swiggy", food, vpas=["Swiggy@ybl"])
    match = run(conn, vpa="swiggy@YBL")
    assert (match.merchant_id, match.category_id, match.confidence, match.stage) == (
        merchant, food, 0.99, "VPA",
    )  # fmt: skip


def test_alias_substring_match_scores_096(conn, food):
    merchant = add_merchant(conn, "Swiggy", food, aliases=["swiggy"])
    match = run(conn, text="SWIGGY ORDER 12")
    assert (match.merchant_id, match.confidence, match.stage) == (merchant, 0.96, "ALIAS")


def test_regex_alias_matches(conn, food):
    add_merchant(conn, "Zomato", food, aliases=[r"re:^zom\w+ order"])
    assert run(conn, text="ZOMATO ORDER 9").stage == "ALIAS"


def test_invalid_oversized_or_late_regex_is_ignored(conn, food):
    add_merchant(conn, "A", food, aliases=["re:(unclosed", "re:" + "a" * 201])
    add_merchant(conn, "B", food, aliases=["re:needle"])
    assert run(conn, text="x" * 250 + "needle").stage == "NONE"
    assert run(conn, text="a" * 201).stage == "NONE"


def test_vpa_stage_beats_alias_stage(conn, food):
    vpa_merchant = add_merchant(conn, "Zed", food, vpas=["z@ybl"])
    add_merchant(conn, "Alpha", food, aliases=["shop"])
    assert run(conn, text="SHOP", vpa="z@ybl").merchant_id == vpa_merchant


def test_no_match_falls_back_to_uncategorized_by_direction(conn):
    debit = run(conn, direction="DEBIT")
    credit = run(conn, direction="CREDIT")
    assert (debit.merchant_id, debit.confidence, debit.stage) == (None, 0.0, "NONE")
    assert debit.category_id == seed.UNCATEGORIZED_EXPENSE_CATEGORY_ID
    assert credit.category_id == seed.UNCATEGORIZED_INCOME_CATEGORY_ID


def test_merchant_without_category_keeps_merchant_id(conn):
    merchant = add_merchant(conn, "Nocat", None, aliases=["nocat"])
    match = run(conn, text="NOCAT")
    assert match.merchant_id == merchant
    assert match.category_id == seed.UNCATEGORIZED_EXPENSE_CATEGORY_ID
    assert match.confidence == 0.0


def test_expense_category_on_credit_row_degrades_to_uncategorized_income(conn, food):
    merchant = add_merchant(conn, "Swiggy", food, aliases=["swiggy"])
    match = run(conn, text="SWIGGY", direction="CREDIT")
    assert match.merchant_id == merchant
    assert match.category_id == seed.UNCATEGORIZED_INCOME_CATEGORY_ID


def test_merchants_are_tried_in_canonical_name_order(conn, food):
    first = add_merchant(conn, "Aaa", food, aliases=["shop"])
    add_merchant(conn, "Bbb", food, aliases=["shop"])
    assert run(conn, text="SHOP").merchant_id == first


def test_seed_is_idempotent(conn):
    seed.seed_system_accounts(conn)
    count = conn.execute("SELECT COUNT(*) FROM categories WHERE is_system_category = 1").fetchone()[0]
    assert count == 2
