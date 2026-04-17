import calendar
import os
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import func

from auth.security import get_password_hash
from database import SessionLocal
from models.dealer import Dealer
from models.dealer_commission import CommissionType, DealerCommission
from models.document import DocumentType, PolicyDocument
from models.policy import Policy, PolicyStatus
from models.policy_transaction import PolicyTransaction, TransactionType
from models.quote import ProductType, Quote, QuoteStatus
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


def _effective_premium(db, policy):
    result = db.query(func.sum(PolicyTransaction.premium_delta)).filter(
        PolicyTransaction.policy_id == policy.id,
        PolicyTransaction.transaction_type.in_(
            [TransactionType.BIND, TransactionType.ENDORSEMENT]
        ),
    ).scalar()
    return Decimal(str(result or 0)).quantize(Decimal("0.01"))


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
    current_data = {
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
            "purchase_date": v.purchase_date if v else None,
            "finance_type": v.finance_type if v else None,
        },
        "product": quote.product.value,
        "product_fields": quote.product_fields,
        "premium": str(quote.calculated_premium),
        "term_months": quote.term_months,
    }
    if quote.dealer:
        current_data["dealer"] = {"id": quote.dealer.id, "name": quote.dealer.name}

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
        product=quote.product,
        status=PolicyStatus.BOUND,
        policy_number=_next_policy_number(db, inception_date.year),
        inception_date=inception_date,
        expiry_date=expiry,
        premium=quote.calculated_premium,
        dealer_fee=commission.dealer_fee,
        broker_commission=commission.broker_commission,
        current_data=current_data,
        dealer_id=quote.dealer_id,
    )
    db.add(policy)
    db.flush()

    quote.status = QuoteStatus.BOUND
    db.add(PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.BIND,
        created_by=user.id,
        data_before=None,
        data_after=current_data,
        premium_delta=Decimal(str(quote.calculated_premium)),
        commission_data={
            "gross_premium": str(commission.gross_premium),
            "dealer_fee": str(commission.dealer_fee),
            "broker_commission": str(commission.broker_commission),
            "net_premium_to_insurer": str(commission.net_premium_to_insurer),
            "total_payable": str(commission.total_payable),
        },
    ))
    db.flush()
    return policy


def _issue(db, policy, user):
    policy.status = PolicyStatus.ISSUED
    db.add(PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.ISSUE,
        created_by=user.id,
        data_before=None,
        data_after=policy.current_data,
        premium_delta=None,
    ))
    db.flush()
    eff = _effective_premium(db, policy)
    pdf = generate_policy_schedule(
        policy,
        tenant_name=policy.tenant.name,
        primary_colour=policy.tenant.primary_colour,
        logo_url=policy.tenant.logo_url,
        effective_premium=eff,
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
    data_before = dict(policy.current_data)
    updated = dict(policy.current_data)
    customer = dict(updated.get("customer", {}))
    if customer_name:
        customer["name"] = customer_name
    if customer_email:
        customer["email"] = customer_email
    updated["customer"] = customer
    policy.current_data = updated

    tx = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.ENDORSEMENT,
        created_by=user.id,
        data_before=data_before,
        data_after=updated,
        premium_delta=Decimal("0"),
        reason_text=reason,
    )
    db.add(tx)
    db.flush()

    pdf = generate_endorsement_certificate(
        policy, tx,
        tenant_name=policy.tenant.name,
        primary_colour=policy.tenant.primary_colour,
        logo_url=policy.tenant.logo_url,
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
    eff = _effective_premium(db, policy)
    refund = (eff * Decimal(days_remaining) / Decimal(total_days)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    tx = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.CANCELLATION,
        created_by=user.id,
        data_before=policy.current_data,
        data_after={**policy.current_data, "cancellation_date": str(cancellation_date)},
        premium_delta=-refund,
        reason_text=reason,
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
    cancellation_date = date.fromisoformat(cancel_tx.data_after["cancellation_date"])
    days_remaining = (policy.expiry_date - cancellation_date).days
    new_expiry = reinstatement_date + timedelta(days=days_remaining)
    total_days = (policy.expiry_date - policy.inception_date).days
    eff = _effective_premium(db, policy)
    reinstatement_premium = (eff * Decimal(days_remaining) / Decimal(total_days)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    policy.status = PolicyStatus.ISSUED
    policy.expiry_date = new_expiry

    tx = PolicyTransaction(
        policy_id=policy.id,
        transaction_type=TransactionType.REINSTATEMENT,
        created_by=user.id,
        data_before={**policy.current_data, "expiry_date": str(cancel_tx.data_after.get("cancellation_date"))},
        data_after={**policy.current_data, "expiry_date": str(new_expiry), "reinstatement_date": str(reinstatement_date)},
        premium_delta=reinstatement_premium,
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
        # ── AUTOSURE UK ───────────────────────────────────────────────────────
        autosure = _get_or_create_tenant(db, "autosure",
            name="Autosure UK",
            primary_colour="#1E4078",
            logo_url="/static/logos/autosure.svg",
            favicon_url="/static/favicons/autosure.ico",
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

        admin_au = _get_or_create_user(db, "admin@autosure.com",
            full_name="Autosure Admin", role=UserRole.TENANT_ADMIN, tenant_id=autosure.id)
        broker_au = _get_or_create_user(db, "broker@autosure.com",
            full_name="Autosure Broker", role=UserRole.BROKER, tenant_id=autosure.id)
        citybroker_au = _get_or_create_user(db, "citybroker@autosure.com",
            full_name="City Broker", role=UserRole.BROKER,
            tenant_id=autosure.id, dealer_id=city_motors.id)

        if db.query(Policy).filter(Policy.tenant_id == autosure.id).count() == 0:
            # 2 QUOTED quotes
            _create_quote(db, autosure, broker_au, ProductType.GAP, 22000, 24,
                "Alice Tanner", "alice@example.com",
                registration="GA21ABC", make="Volkswagen", model="Golf", year=2021,
                finance_type="PCP", product_fields={"settlement_figure": 18000})
            _create_quote(db, autosure, broker_au, ProductType.VRI, 35000, 12,
                "Bob Keane", "bob@example.com",
                registration="VR22XYZ", make="BMW", model="3 Series", year=2022)

            # 1 BOUND policy
            q_bound = _create_quote(db, autosure, broker_au, ProductType.TYRE_PLUS, 18000, 12,
                "Carol Webb", "carol@example.com",
                registration="TP20DEF", make="Honda", model="Civic", year=2020)
            _bind(db, q_bound, broker_au, inception_date=date(2025, 3, 1))

            # 1 ISSUED policy — dealer-attributed via City Motors
            q_issued = _create_quote(db, autosure, citybroker_au, ProductType.GAP, 25000, 36,
                "David Singh", "david@example.com",
                registration="GA23GHI", make="Toyota", model="Corolla", year=2023,
                finance_type="HP", product_fields={"settlement_figure": 21000},
                dealer=city_motors)
            p_issued = _bind(db, q_issued, citybroker_au, inception_date=date(2025, 2, 1))
            _issue(db, p_issued, citybroker_au)

            # 1 ISSUED policy with endorsement + cancellation + reinstatement history
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

        # ── DRIVESHIELD ───────────────────────────────────────────────────────
        driveshield = _get_or_create_tenant(db, "driveshield",
            name="DriveShield",
            primary_colour="#0D7C5F",
            logo_url="/static/logos/driveshield.svg",
            favicon_url="/static/favicons/driveshield.ico",
            allowed_products=["GAP", "TYRE_ESSENTIAL", "TYRE_PLUS", "COSMETIC"],
        )

        shield_london = _get_or_create_dealer(db, driveshield.id, "Shield Direct London",
            contact_email="info@shielddirect.co.uk")
        _add_commission(db, shield_london.id, "PERCENTAGE", "18.0000")

        shield_glasgow = _get_or_create_dealer(db, driveshield.id, "Shield North Glasgow",
            contact_email="info@shieldnorth.co.uk")
        _add_commission(db, shield_glasgow.id, "PERCENTAGE", "16.0000")

        admin_ds = _get_or_create_user(db, "admin@driveshield.com",
            full_name="DriveShield Admin", role=UserRole.TENANT_ADMIN, tenant_id=driveshield.id)
        broker_ds = _get_or_create_user(db, "broker@driveshield.com",
            full_name="DriveShield Broker", role=UserRole.BROKER, tenant_id=driveshield.id)
        shieldbroker_ds = _get_or_create_user(db, "shieldbroker@driveshield.com",
            full_name="Shield Direct Broker", role=UserRole.BROKER,
            tenant_id=driveshield.id, dealer_id=shield_london.id)

        if db.query(Policy).filter(Policy.tenant_id == driveshield.id).count() == 0:
            # 1 QUOTED quote
            _create_quote(db, driveshield, broker_ds, ProductType.GAP, 16000, 12,
                "Frank Obi", "frank@example.com",
                registration="GA21DSH", make="Nissan", model="Juke", year=2021,
                finance_type="PCP", product_fields={"settlement_figure": 13000})

            # 1 ISSUED policy — dealer-attributed via Shield Direct London
            q_ds_issued = _create_quote(db, driveshield, shieldbroker_ds, ProductType.TYRE_ESSENTIAL, 19000, 12,
                "Grace Kim", "grace@example.com",
                registration="TE22DSH", make="Hyundai", model="Tucson", year=2022,
                dealer=shield_london)
            p_ds_issued = _bind(db, q_ds_issued, shieldbroker_ds, inception_date=date(2025, 1, 10))
            _issue(db, p_ds_issued, shieldbroker_ds)

            # 1 CANCELLED policy
            q_ds_cancel = _create_quote(db, driveshield, broker_ds, ProductType.COSMETIC, 21000, 12,
                "Harry Patel", "harry@example.com",
                registration="CO23DSH", make="Kia", model="Sportage", year=2023)
            p_ds_cancel = _bind(db, q_ds_cancel, broker_ds, inception_date=date(2024, 10, 1))
            _issue(db, p_ds_cancel, broker_ds)
            _cancel(db, p_ds_cancel, admin_ds,
                cancellation_date=date(2025, 1, 5), reason="Vehicle sold")

        # ── PREMIUMCOVER ──────────────────────────────────────────────────────
        premiumcover = _get_or_create_tenant(db, "premiumcover",
            name="PremiumCover",
            primary_colour="#6B1E1E",
            logo_url="/static/logos/premiumcover.svg",
            favicon_url="/static/favicons/premiumcover.ico",
            allowed_products=["GAP", "VRI", "TLP"],
        )

        elite_mayfair = _get_or_create_dealer(db, premiumcover.id, "Elite Autos Mayfair",
            contact_email="info@eliteautos.co.uk")
        _add_commission(db, elite_mayfair.id, "PERCENTAGE", "20.0000")

        prestige_surrey = _get_or_create_dealer(db, premiumcover.id, "Prestige South Surrey",
            contact_email="info@prestigesurrey.co.uk")
        _add_commission(db, prestige_surrey.id, "PERCENTAGE", "18.0000")

        _get_or_create_user(db, "admin@premiumcover.com",
            full_name="PremiumCover Admin", role=UserRole.TENANT_ADMIN, tenant_id=premiumcover.id)
        broker_pc = _get_or_create_user(db, "broker@premiumcover.com",
            full_name="PremiumCover Broker", role=UserRole.BROKER, tenant_id=premiumcover.id)

        if db.query(Policy).filter(Policy.tenant_id == premiumcover.id).count() == 0:
            # 1 QUOTED quote (VRI)
            _create_quote(db, premiumcover, broker_pc, ProductType.VRI, 65000, 24,
                "Isabella Zhao", "isabella@example.com",
                registration="VR23PCO", make="Audi", model="Q7", year=2023)

            # 1 ISSUED policy (GAP, dealer-attributed via Elite Autos Mayfair)
            q_pc_issued = _create_quote(db, premiumcover, broker_pc, ProductType.GAP, 55000, 24,
                "James Harrow", "james@example.com",
                registration="GA22PCO", make="Porsche", model="Cayenne", year=2022,
                finance_type="PCP", product_fields={"settlement_figure": 48000},
                dealer=elite_mayfair)
            p_pc_issued = _bind(db, q_pc_issued, broker_pc, inception_date=date(2025, 2, 15))
            _issue(db, p_pc_issued, broker_pc)

        db.commit()
        print("Seeded: Autosure UK, DriveShield, PremiumCover")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
