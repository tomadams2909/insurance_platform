from decimal import Decimal

import pytest

from models.dealer import Dealer
from models.dealer_commission import DealerCommission, CommissionType
from models.quote import ProductType
from services.commission import calculate_commission


@pytest.fixture
def dealer(db, test_tenant):
    d = Dealer(tenant_id=test_tenant.id, name="Test Motors")
    db.add(d)
    db.flush()
    return d


@pytest.fixture
def dealer_with_default_rate(db, dealer):
    """Dealer with 15% commission on all products."""
    commission = DealerCommission(
        dealer_id=dealer.id,
        product=None,
        commission_type=CommissionType.PERCENTAGE,
        commission_rate=Decimal("15.0000"),
        is_active=True,
    )
    db.add(commission)
    db.flush()
    return dealer


@pytest.fixture
def dealer_with_flat_fee(db, dealer):
    """Dealer with £50 flat fee on all products."""
    commission = DealerCommission(
        dealer_id=dealer.id,
        product=None,
        commission_type=CommissionType.FLAT_FEE,
        commission_rate=Decimal("50.0000"),
        is_active=True,
    )
    db.add(commission)
    db.flush()
    return dealer


@pytest.fixture
def dealer_with_product_override(db, dealer):
    """Dealer with 10% default, 20% override on GAP."""
    default = DealerCommission(
        dealer_id=dealer.id,
        product=None,
        commission_type=CommissionType.PERCENTAGE,
        commission_rate=Decimal("10.0000"),
        is_active=True,
    )
    gap_override = DealerCommission(
        dealer_id=dealer.id,
        product="GAP",
        commission_type=CommissionType.PERCENTAGE,
        commission_rate=Decimal("20.0000"),
        is_active=True,
    )
    db.add(default)
    db.add(gap_override)
    db.flush()
    return dealer


class TestPercentageCommission:
    def test_dealer_fee_is_correct(self, db, test_tenant, dealer_with_default_rate):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_default_rate, test_tenant, db)
        assert result.dealer_fee == Decimal("150.00")

    def test_broker_commission_is_correct(self, db, test_tenant, dealer_with_default_rate):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_default_rate, test_tenant, db)
        assert result.broker_commission == Decimal("150.00")

    def test_net_to_insurer_is_gross_minus_broker(self, db, test_tenant, dealer_with_default_rate):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_default_rate, test_tenant, db)
        assert result.net_premium_to_insurer == Decimal("850.00")

    def test_total_payable_is_gross_plus_dealer_fee(self, db, test_tenant, dealer_with_default_rate):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_default_rate, test_tenant, db)
        assert result.total_payable == Decimal("1150.00")

    def test_larger_premium(self, db, test_tenant, dealer_with_default_rate):
        # £3000 premium, 15% dealer, 15% broker
        result = calculate_commission(Decimal("3000"), ProductType.GAP, dealer_with_default_rate, test_tenant, db)
        assert result.dealer_fee == Decimal("450.00")
        assert result.broker_commission == Decimal("450.00")
        assert result.net_premium_to_insurer == Decimal("2550.00")
        assert result.total_payable == Decimal("3450.00")


class TestFlatFeeCommission:
    def test_dealer_fee_is_flat_amount(self, db, test_tenant, dealer_with_flat_fee):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_flat_fee, test_tenant, db)
        assert result.dealer_fee == Decimal("50.00")

    def test_broker_commission_still_percentage_of_premium(self, db, test_tenant, dealer_with_flat_fee):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_flat_fee, test_tenant, db)
        assert result.broker_commission == Decimal("150.00")

    def test_net_to_insurer_unaffected_by_flat_fee(self, db, test_tenant, dealer_with_flat_fee):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_flat_fee, test_tenant, db)
        assert result.net_premium_to_insurer == Decimal("850.00")

    def test_total_payable(self, db, test_tenant, dealer_with_flat_fee):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_flat_fee, test_tenant, db)
        assert result.total_payable == Decimal("1050.00")


class TestProductOverride:
    def test_product_specific_rate_used_over_default(self, db, test_tenant, dealer_with_product_override):
        # GAP has 20% override, default is 10% — should use 20%
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_product_override, test_tenant, db)
        assert result.dealer_fee == Decimal("200.00")

    def test_default_rate_used_for_other_products(self, db, test_tenant, dealer_with_product_override):
        # COSMETIC has no override — should use 10% default
        result = calculate_commission(
            Decimal("1000"), ProductType.COSMETIC, dealer_with_product_override, test_tenant, db
        )
        assert result.dealer_fee == Decimal("100.00")


class TestNoDealer:
    def test_dealer_fee_is_zero(self, db, test_tenant):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, None, test_tenant, db)
        assert result.dealer_fee == Decimal("0.00")

    def test_broker_commission_still_applied(self, db, test_tenant):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, None, test_tenant, db)
        assert result.broker_commission == Decimal("150.00")

    def test_net_to_insurer(self, db, test_tenant):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, None, test_tenant, db)
        assert result.net_premium_to_insurer == Decimal("850.00")

    def test_total_payable_equals_gross_when_no_dealer(self, db, test_tenant):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, None, test_tenant, db)
        assert result.total_payable == Decimal("1000.00")


class TestInvariants:
    def test_net_plus_broker_always_equals_gross(self, db, test_tenant, dealer_with_default_rate):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_default_rate, test_tenant, db)
        assert result.net_premium_to_insurer + result.broker_commission == result.gross_premium

    def test_total_payable_equals_gross_plus_dealer_fee(self, db, test_tenant, dealer_with_default_rate):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_default_rate, test_tenant, db)
        assert result.total_payable == result.gross_premium + result.dealer_fee

    def test_gross_premium_is_set_correctly(self, db, test_tenant, dealer_with_default_rate):
        result = calculate_commission(Decimal("1000"), ProductType.GAP, dealer_with_default_rate, test_tenant, db)
        assert result.gross_premium == Decimal("1000")
