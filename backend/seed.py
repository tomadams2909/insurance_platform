import calendar
import os
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from auth.security import get_password_hash
from database import SessionLocal
from models.dealer import Dealer
from models.dealer_commission import CommissionType, DealerCommission
from models.document import DocumentType, PolicyDocument
from models.policy import Policy, PolicyStatus
from models.policy_transaction import PolicyTransaction, TransactionType
from models.quote import ProductType, Quote, QuoteStatus, PaymentType
from models.tenant import Tenant
from models.user import User, UserRole
from models.vehicle import Vehicle
from services.commission import calculate_commission
from services.document import (
    generate_cancellation_notice,
    generate_endorsement_certificate,
    generate_policy_schedule,
    generate_reinstatement_notice,
)
from services.pricing import calculate_premium, get_vehicle_category

PASSWORD = "Demo1234!"


def _get_or_create_tenant(db, slug, **kwargs):
    tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if not tenant:
        tenant = Tenant(slug=slug, **kwargs)
        db.add(tenant)
        db.flush()
    return tenant


def _get_or_create_user(db, email, **kwargs):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, hashed_password=get_password_hash(PASSWORD), **kwargs)
        db.add(user)
        db.flush()
    return user


def _get_or_create_dealer(db, tenant_id, name, **kwargs):
    dealer = db.query(Dealer).filter(
        Dealer.tenant_id == tenant_id, Dealer.name == name
    ).first()
    if not dealer:
        dealer = Dealer(tenant_id=tenant_id, name=name, **kwargs)
        db.add(dealer)
        db.flush()
    return dealer


def _add_commission(db, dealer_id, commission_type, commission_rate, product=None):
    product_val = product.value if product else None
    existing = db.query(DealerCommission).filter(
        DealerCommission.dealer_id == dealer_id,
        DealerCommission.product == product_val,
        DealerCommission.is_active.is_(True),
    ).first()
    if existing:
        return existing
    commission = DealerCommission(
        dealer_id=dealer_id,
        product=product_val,
        commission_type=CommissionType[commission_type],
        commission_rate=commission_rate,
        is_active=True,
    )
    db.add(commission)
    db.flush()
    return commission


def _add_months(d, months):
    month = d.month + months
    year = d.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _next_policy_number(db, year):
    prefix = f"POL-{year}-"
    count = db.query(Policy).filter(Policy.policy_number.like(f"{prefix}%")).count()
    return f"{prefix}{str(count + 1).zfill(5)}"


def _create_quote(
    db, tenant, user, product, purchase_price, term_months,
    customer_name, customer_email,
    registration=None, make=None, model=None, year=None,
    purchase_date=None, finance_type=None, product_fields=None, dealer=None,
):
    price = Decimal(str(purchase_price))
    cat = get_vehicle_category(price)
    premium = calculate_premium(product.value, price, term_months)

    quote = Quote(
        tenant_id=tenant.id,
        product=product,
        status=QuoteStatus.QUOTED,
        customer_name=customer_name,
        customer_dob="1985-06-15",
        customer_email=customer_email,
        customer_address={"line1": "10 Example Street", "city": "London", "postcode": "EC1A 1BB"},
        term_months=term_months,
        vehicle_category=cat,
        product_fields=product_fields,
        calculated_premium=premium,
        created_by=user.id,
        dealer_id=dealer.id if dealer else None,
        payment_type=PaymentType.CASH,
    )
    db.add(quote)
    db.flush()

    db.add(Vehicle(
        quote_id=quote.id,
        registration=registration or "AB21CDE",
        make=make or "Ford",
        model=model or "Focus",
        year=year or 2021,
        purchase_price=price,
        purchase_date=purchase_date or "2021-06-01",
        finance_type=finance_type,
    ))
    db.flush()
    return quote


def _bind(db, quote, user, inception_date):
    expiry = _add_months(inception_date, quote.term_months)
    v = quote.vehicle
    policy_data = {
        "customer": {
            "name": quote.customer_name,
            "dob": quote.customer_dob,
            "email": quote.customer_email,
            "address": quote.customer_address,
        },
        "vehicle": {
            "registration": v.registration if v else None,
            "make": v.make if v else None,
            "model": v.model if v else None,
            "year": v.year if v else None,
            "purchase_price": str(v.purchase_price) if v else None,
            "purchase_date": str(v.purchase_date) if v else None,
            "finance_type": v.finance_type if v else None,
        },
        "product_fields": quote.product_fields,
    }
    if quote.dealer:
        policy_data["dealer"] = {"id": quote.dealer.id, "name": quote.dealer.name}

    commission = calculate_commission(
        premium=Decimal(str(quote.calculated_premium)),
        product=quote.product,
        dealer=quote.dealer,
        tenant=quote.tenant,
        db=db,
    )

    policy = Policy(
        quote_id=quote.id,
        tenant_id=quote.tenant_id,
        dealer_id=quote.dealer_id,
        product=quote.product,
        status=PolicyStatus.BOUND,
        policy_number=_next_policy_number(db, inception_date.year),
        inception_date=inception_date,
        expiry_date=expiry,
        term_months=quote.term_months,
        payment_type=quote.payment_type,
        premium=quote.calculated_premium,
        dealer_fee=commission.dealer_fee,
        broker_commission=commission.broker_commission,
        dealer_fee_rate=commission.dealer_fee_rate,
        broker_commission_rate=commission.broker_commission_rate,
        policy_data=policy_data,
    )
    db.add(policy)
    db.flush()

    quote.status = QuoteStatus.BOUND
    db.add(PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.BIND,
        created_by=user.id,
        premium_delta=Decimal(str(quote.calculated_premium)),
        dealer_fee_delta=commission.dealer_fee,
        broker_commission_delta=commission.broker_commission,
        dealer_fee_rate=commission.dealer_fee_rate,
        broker_commission_rate=commission.broker_commission_rate,
        snapshot=policy_data,
    ))
    db.flush()
    return policy


def _issue(db, policy, user):
    policy.status = PolicyStatus.ISSUED
    db.add(PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.ISSUE,
        created_by=user.id,
        snapshot=policy.policy_data,
    ))
    db.flush()
    pdf = generate_policy_schedule(
        policy,
        tenant_name=policy.tenant.name,
        primary_colour=policy.tenant.primary_colour,
        logo_url=policy.tenant.logo_url,
        effective_premium=Decimal(str(policy.premium)),
    )
    db.add(PolicyDocument(
        policy_id=policy.id,
        document_type=DocumentType.POLICY_SCHEDULE,
        filename=f"{policy.policy_number}_schedule.pdf",
        content=pdf,
    ))
    db.flush()
    return policy


def _endorse(db, policy, user, reason, customer_name=None, customer_email=None):
    before_snapshot = dict(policy.policy_data)
    updated = dict(policy.policy_data)
    customer = dict(updated.get("customer", {}))
    if customer_name:
        customer["name"] = customer_name
    if customer_email:
        customer["email"] = customer_email
    updated["customer"] = customer
    policy.policy_data = updated

    tx = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.ENDORSEMENT,
        created_by=user.id,
        premium_delta=Decimal("0"),
        dealer_fee_delta=Decimal("0"),
        broker_commission_delta=Decimal("0"),
        dealer_fee_rate=policy.dealer_fee_rate,
        broker_commission_rate=policy.broker_commission_rate,
        reason_text=reason,
        snapshot=updated,
    )
    db.add(tx)
    db.flush()

    pdf = generate_endorsement_certificate(
        policy, tx,
        tenant_name=policy.tenant.name,
        primary_colour=policy.tenant.primary_colour,
        logo_url=policy.tenant.logo_url,
        before_snapshot=before_snapshot,
    )
    db.add(PolicyDocument(
        policy_id=policy.id,
        document_type=DocumentType.ENDORSEMENT_CERTIFICATE,
        filename=f"{policy.policy_number}_endorsement_{tx.id}.pdf",
        content=pdf,
    ))
    db.flush()
    return policy


def _cancel(db, policy, user, cancellation_date, reason):
    policy.status = PolicyStatus.CANCELLED
    total_days = (policy.expiry_date - policy.inception_date).days
    days_remaining = (policy.expiry_date - cancellation_date).days
    eff = Decimal(str(policy.premium))
    refund = (eff * Decimal(days_remaining) / Decimal(total_days)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    old_commission = calculate_commission(eff, policy.product, policy.dealer, policy.tenant, db)
    clawback_ratio = Decimal(days_remaining) / Decimal(total_days)
    dealer_fee_delta = -(old_commission.dealer_fee * clawback_ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    broker_commission_delta = -(old_commission.broker_commission * clawback_ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    snapshot = {**policy.policy_data, "cancellation_date": str(cancellation_date)}
    tx = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.CANCELLATION,
        created_by=user.id,
        premium_delta=-refund,
        dealer_fee_delta=dealer_fee_delta,
        broker_commission_delta=broker_commission_delta,
        dealer_fee_rate=policy.dealer_fee_rate,
        broker_commission_rate=policy.broker_commission_rate,
        reason_text=reason,
        snapshot=snapshot,
    )
    db.add(tx)
    db.flush()

    pdf = generate_cancellation_notice(
        policy, tx,
        tenant_name=policy.tenant.name,
        primary_colour=policy.tenant.primary_colour,
        logo_url=policy.tenant.logo_url,
    )
    db.add(PolicyDocument(
        policy_id=policy.id,
        document_type=DocumentType.CANCELLATION_NOTICE,
        filename=f"{policy.policy_number}_cancellation.pdf",
        content=pdf,
    ))
    db.flush()
    return policy, tx


def _reinstate(db, policy, user, cancel_tx, reinstatement_date):
    cancellation_date = date.fromisoformat(cancel_tx.snapshot["cancellation_date"])
    days_remaining = (policy.expiry_date - cancellation_date).days
    new_expiry = reinstatement_date + timedelta(days=days_remaining)
    total_days = (policy.expiry_date - policy.inception_date).days
    eff = Decimal(str(policy.premium))
    reinstatement_premium = (eff * Decimal(days_remaining) / Decimal(total_days)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    old_commission = calculate_commission(eff, policy.product, policy.dealer, policy.tenant, db)
    recharge_ratio = Decimal(days_remaining) / Decimal(total_days)
    dealer_fee_delta = (old_commission.dealer_fee * recharge_ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    broker_commission_delta = (old_commission.broker_commission * recharge_ratio).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    policy.status = PolicyStatus.ISSUED
    policy.expiry_date = new_expiry
    snapshot = {**policy.policy_data, "expiry_date": str(new_expiry), "reinstatement_date": str(reinstatement_date)}

    tx = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.REINSTATEMENT,
        created_by=user.id,
        premium_delta=reinstatement_premium,
        dealer_fee_delta=dealer_fee_delta,
        broker_commission_delta=broker_commission_delta,
        dealer_fee_rate=policy.dealer_fee_rate,
        broker_commission_rate=policy.broker_commission_rate,
        snapshot=snapshot,
    )
    db.add(tx)
    db.flush()

    pdf = generate_reinstatement_notice(
        policy, tx,
        tenant_name=policy.tenant.name,
        primary_colour=policy.tenant.primary_colour,
        logo_url=policy.tenant.logo_url,
    )
    db.add(PolicyDocument(
        policy_id=policy.id,
        document_type=DocumentType.REINSTATEMENT_NOTICE,
        filename=f"{policy.policy_number}_reinstatement.pdf",
        content=pdf,
    ))
    db.flush()
    return policy


def seed():
    db = SessionLocal()
    try:
        # ── INSURANCE CO. LTD ─────────────────────────────────────────────────
        autosure = _get_or_create_tenant(db, "insuranceco",
            name="Insurance Co. Ltd",
            primary_colour="#1E4078",
            logo_url="/static/logos/insuranceco_logo.svg",
            favicon_url="/static/favicons/insuranceco.svg",
            allowed_products=None,
        )

        city_motors = _get_or_create_dealer(db, autosure.id, "City Motors Manchester",
            contact_email="fleet@citymotors.co.uk")
        _add_commission(db, city_motors.id, "PERCENTAGE", "15.0000")

        prestige_leeds = _get_or_create_dealer(db, autosure.id, "Prestige Auto Leeds",
            contact_email="fleet@prestigeleeds.co.uk")
        _add_commission(db, prestige_leeds.id, "PERCENTAGE", "12.0000")
        _add_commission(db, prestige_leeds.id, "FLAT_FEE", "50.0000", product=ProductType.TYRE_ESSENTIAL)
        _add_commission(db, prestige_leeds.id, "FLAT_FEE", "50.0000", product=ProductType.TYRE_PLUS)

        valley_cars = _get_or_create_dealer(db, autosure.id, "Valley Cars Birmingham",
            contact_email="fleet@valleycars.co.uk")
        _add_commission(db, valley_cars.id, "PERCENTAGE", "14.0000")

        admin_au = _get_or_create_user(db, "admin@insuranceco.com",
            full_name="Insurance Co. Admin", role=UserRole.TENANT_ADMIN, tenant_id=autosure.id)
        broker_au = _get_or_create_user(db, "broker@insuranceco.com",
            full_name="Insurance Co. Broker", role=UserRole.BROKER, tenant_id=autosure.id)
        citybroker_au = _get_or_create_user(db, "citybroker@insuranceco.com",
            full_name="City Broker", role=UserRole.BROKER,
            tenant_id=autosure.id, dealer_id=city_motors.id)

        if db.query(Policy).filter(Policy.tenant_id == autosure.id).count() == 0:
            _create_quote(db, autosure, broker_au, ProductType.GAP, 22000, 24,
                "Alice Tanner", "alice@example.com",
                registration="GA21ABC", make="Volkswagen", model="Golf", year=2021,
                finance_type="PCP", product_fields={"loan_amount": 18000})
            _create_quote(db, autosure, broker_au, ProductType.VRI, 35000, 12,
                "Bob Keane", "bob@example.com",
                registration="VR22XYZ", make="BMW", model="3 Series", year=2022)

            q_bound = _create_quote(db, autosure, broker_au, ProductType.TYRE_PLUS, 18000, 12,
                "Carol Webb", "carol@example.com",
                registration="TP20DEF", make="Honda", model="Civic", year=2020)
            _bind(db, q_bound, broker_au, inception_date=date(2025, 3, 1))

            q_issued = _create_quote(db, autosure, citybroker_au, ProductType.GAP, 25000, 36,
                "David Singh", "david@example.com",
                registration="GA23GHI", make="Toyota", model="Corolla", year=2023,
                finance_type="HP", product_fields={"loan_amount": 21000},
                dealer=city_motors)
            p_issued = _bind(db, q_issued, citybroker_au, inception_date=date(2025, 2, 1))
            _issue(db, p_issued, citybroker_au)

            q_rich = _create_quote(db, autosure, broker_au, ProductType.COSMETIC, 28000, 24,
                "Eve Morton", "eve@example.com",
                registration="CO22JKL", make="Mercedes", model="A-Class", year=2022)
            p_rich = _bind(db, q_rich, broker_au, inception_date=date(2024, 6, 1))
            _issue(db, p_rich, broker_au)
            _endorse(db, p_rich, admin_au, reason="Customer email update",
                customer_email="eve.morton@example.com")
            p_rich, cancel_tx = _cancel(db, p_rich, admin_au,
                cancellation_date=date(2024, 9, 15), reason="Customer request")
            _reinstate(db, p_rich, admin_au, cancel_tx,
                reinstatement_date=date(2024, 10, 1))

        # ── CAR COVER LTD ─────────────────────────────────────────────────────
        carcover = _get_or_create_tenant(db, "carcover",
            name="Car Cover Ltd",
            primary_colour="#0D7C5F",
            logo_url="/static/logos/carcover_logo.svg",
            favicon_url="/static/favicons/carcover.svg",
            allowed_products=["GAP", "TYRE_ESSENTIAL", "TYRE_PLUS", "COSMETIC"],
        )

        shield_london = _get_or_create_dealer(db, carcover.id, "Shield Direct London",
            contact_email="info@shielddirect.co.uk")
        _add_commission(db, shield_london.id, "PERCENTAGE", "18.0000")

        shield_glasgow = _get_or_create_dealer(db, carcover.id, "Shield North Glasgow",
            contact_email="info@shieldnorth.co.uk")
        _add_commission(db, shield_glasgow.id, "PERCENTAGE", "16.0000")

        admin_ds = _get_or_create_user(db, "admin@carcover.com",
            full_name="Car Cover Admin", role=UserRole.TENANT_ADMIN, tenant_id=carcover.id)
        broker_ds = _get_or_create_user(db, "broker@carcover.com",
            full_name="Car Cover Broker", role=UserRole.BROKER, tenant_id=carcover.id)
        shieldbroker_ds = _get_or_create_user(db, "shieldbroker@carcover.com",
            full_name="Shield Direct Broker", role=UserRole.BROKER,
            tenant_id=carcover.id, dealer_id=shield_london.id)

        if db.query(Policy).filter(Policy.tenant_id == carcover.id).count() == 0:
            _create_quote(db, carcover, broker_ds, ProductType.GAP, 16000, 12,
                "Frank Obi", "frank@example.com",
                registration="GA21DSH", make="Nissan", model="Juke", year=2021,
                finance_type="PCP", product_fields={"loan_amount": 13000})

            q_ds_issued = _create_quote(db, carcover, shieldbroker_ds, ProductType.TYRE_ESSENTIAL, 19000, 12,
                "Grace Kim", "grace@example.com",
                registration="TE22DSH", make="Hyundai", model="Tucson", year=2022,
                dealer=shield_london)
            p_ds_issued = _bind(db, q_ds_issued, shieldbroker_ds, inception_date=date(2025, 1, 10))
            _issue(db, p_ds_issued, shieldbroker_ds)

            q_ds_cancel = _create_quote(db, carcover, broker_ds, ProductType.COSMETIC, 21000, 12,
                "Harry Patel", "harry@example.com",
                registration="CO23DSH", make="Kia", model="Sportage", year=2023)
            p_ds_cancel = _bind(db, q_ds_cancel, broker_ds, inception_date=date(2024, 10, 1))
            _issue(db, p_ds_cancel, broker_ds)
            _cancel(db, p_ds_cancel, admin_ds,
                cancellation_date=date(2025, 1, 5), reason="Vehicle sold")

        # ── AUTO INSURANCE LTD ────────────────────────────────────────────────
        autoinsurance = _get_or_create_tenant(db, "autoinsurance",
            name="Auto Insurance Ltd",
            primary_colour="#6B1E1E",
            logo_url="/static/logos/autoinsurance_logo.svg",
            favicon_url="/static/favicons/autoinsurance.svg",
            allowed_products=["GAP", "VRI", "TLP"],
        )

        elite_mayfair = _get_or_create_dealer(db, autoinsurance.id, "Elite Autos Mayfair",
            contact_email="info@eliteautos.co.uk")
        _add_commission(db, elite_mayfair.id, "PERCENTAGE", "20.0000")

        prestige_surrey = _get_or_create_dealer(db, autoinsurance.id, "Prestige South Surrey",
            contact_email="info@prestigesurrey.co.uk")
        _add_commission(db, prestige_surrey.id, "PERCENTAGE", "18.0000")

        _get_or_create_user(db, "admin@autoinsurance.com",
            full_name="Auto Insurance Admin", role=UserRole.TENANT_ADMIN, tenant_id=autoinsurance.id)
        broker_pc = _get_or_create_user(db, "broker@autoinsurance.com",
            full_name="Auto Insurance Broker", role=UserRole.BROKER, tenant_id=autoinsurance.id)

        if db.query(Policy).filter(Policy.tenant_id == autoinsurance.id).count() == 0:
            _create_quote(db, autoinsurance, broker_pc, ProductType.VRI, 65000, 24,
                "Isabella Zhao", "isabella@example.com",
                registration="VR23PCO", make="Audi", model="Q7", year=2023)

            q_pc_issued = _create_quote(db, autoinsurance, broker_pc, ProductType.GAP, 55000, 24,
                "James Harrow", "james@example.com",
                registration="GA22PCO", make="Porsche", model="Cayenne", year=2022,
                finance_type="PCP", product_fields={"loan_amount": 48000},
                dealer=elite_mayfair)
            p_pc_issued = _bind(db, q_pc_issued, broker_pc, inception_date=date(2025, 2, 15))
            _issue(db, p_pc_issued, broker_pc)

        db.commit()
        print("Seeded: Insurance Co. Ltd, Car Cover Ltd, Auto Insurance Ltd")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
