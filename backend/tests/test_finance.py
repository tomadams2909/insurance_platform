from decimal import Decimal

import pytest

from services.finance import calculate_finance, REPRESENTATIVE_APR, FinanceBreakdown


def test_basic_finance_breakdown():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("100.00"),
        term_months=12,
        apr=Decimal("9.9"),
    )
    assert result.financed_amount == Decimal("900.00")
    assert result.finance_charge > Decimal("0")
    assert result.total_repayable > Decimal("900.00")


def test_monthly_payments_sum_to_total_repayable():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("100.00"),
        term_months=12,
        apr=Decimal("9.9"),
    )
    assert result.monthly_payment * 12 == result.total_repayable


def test_finance_charge_equals_total_repayable_minus_financed_amount():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("100.00"),
        term_months=12,
        apr=Decimal("9.9"),
    )
    assert result.finance_charge == result.total_repayable - result.financed_amount


def test_zero_deposit_financed_amount_equals_principal():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("0.00"),
        term_months=12,
        apr=Decimal("9.9"),
    )
    assert result.financed_amount == Decimal("1000.00")


def test_finance_charge_always_positive():
    result = calculate_finance(
        principal=Decimal("5000.00"),
        deposit=Decimal("500.00"),
        term_months=24,
        apr=REPRESENTATIVE_APR,
    )
    assert result.finance_charge > Decimal("0")


def test_representative_apr_stored_on_result():
    result = calculate_finance(
        principal=Decimal("2000.00"),
        deposit=Decimal("200.00"),
        term_months=12,
    )
    assert result.apr == REPRESENTATIVE_APR


def test_custom_apr_used():
    result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("0.00"),
        term_months=12,
        apr=Decimal("19.9"),
    )
    default_result = calculate_finance(
        principal=Decimal("1000.00"),
        deposit=Decimal("0.00"),
        term_months=12,
        apr=REPRESENTATIVE_APR,
    )
    assert result.monthly_payment > default_result.monthly_payment
    assert result.finance_charge > default_result.finance_charge


def test_longer_term_produces_higher_finance_charge():
    result_12 = calculate_finance(Decimal("1000"), Decimal("0"), 12)
    result_36 = calculate_finance(Decimal("1000"), Decimal("0"), 36)
    assert result_36.finance_charge > result_12.finance_charge


def test_longer_term_produces_lower_monthly_payment():
    result_12 = calculate_finance(Decimal("1000"), Decimal("0"), 12)
    result_36 = calculate_finance(Decimal("1000"), Decimal("0"), 36)
    assert result_36.monthly_payment < result_12.monthly_payment


def test_money_values_rounded_to_2dp():
    result = calculate_finance(Decimal("999.99"), Decimal("123.45"), 12)
    for value in (result.financed_amount, result.monthly_payment, result.finance_charge, result.total_repayable):
        assert value == value.quantize(Decimal("0.01"))


def test_returns_finance_breakdown_instance():
    result = calculate_finance(Decimal("1000"), Decimal("0"), 12)
    assert isinstance(result, FinanceBreakdown)
