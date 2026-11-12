import pytest

from app.finance.safe_to_spend import calculate_safe_to_spend_minor


def test_surplus_case_returns_disposable_cash_and_daily_burn():
    # Arrange
    liquid = 100_000_00
    card = 20_000_00
    obligations = 15_000_00
    goals = 5_000_00
    days = 10

    # Act
    result = calculate_safe_to_spend_minor(liquid, card, obligations, goals, days)

    # Assert
    assert result.safe_to_spend_minor == 60_000_00
    assert result.daily_safe_burn_minor == 6_000_00
    assert result.is_liquidity_deficit is False
    assert result.deficit_minor == 0
    assert result.card_liability_minor == 20_000_00
    assert result.upcoming_obligations_minor == 15_000_00
    assert result.goal_locks_minor == 5_000_00
    assert result.liquid_cash_minor == 100_000_00


def test_deficit_case_clamps_safe_to_spend_to_zero_and_reports_deficit():
    # Arrange
    liquid = 10_000_00
    card = 8_000_00
    obligations = 5_000_00
    goals = 0

    # Act
    result = calculate_safe_to_spend_minor(liquid, card, obligations, goals, 5)

    # Assert
    assert result.safe_to_spend_minor == 0
    assert result.daily_safe_burn_minor == 0
    assert result.is_liquidity_deficit is True
    assert result.deficit_minor == 3_000_00


def test_card_balance_given_as_negative_gives_same_result_as_positive():
    # Arrange
    positive = calculate_safe_to_spend_minor(50_000_00, 12_000_00, 1_000_00, 500_00, 20)

    # Act
    negative = calculate_safe_to_spend_minor(50_000_00, -12_000_00, 1_000_00, 500_00, 20)

    # Assert
    assert negative == positive


def test_days_remaining_below_one_is_clamped_to_one():
    # Arrange
    days_zero = 0
    days_negative = -4

    # Act
    result_zero = calculate_safe_to_spend_minor(1_000_00, 0, 0, 0, days_zero)
    result_negative = calculate_safe_to_spend_minor(1_000_00, 0, 0, 0, days_negative)

    # Assert
    assert result_zero.daily_safe_burn_minor == 1_000_00
    assert result_negative.daily_safe_burn_minor == 1_000_00


def test_float_input_raises_type_error():
    with pytest.raises(TypeError):
        calculate_safe_to_spend_minor(1000.5, 0, 0, 0, 10)


def test_bool_input_raises_type_error():
    with pytest.raises(TypeError):
        calculate_safe_to_spend_minor(1000, 0, 0, False, 10)


def test_negative_obligations_raise_value_error():
    with pytest.raises(ValueError):
        calculate_safe_to_spend_minor(1000, 0, -1, 0, 10)


def test_negative_goal_locks_raise_value_error():
    with pytest.raises(ValueError):
        calculate_safe_to_spend_minor(1000, 0, 0, -1, 10)
