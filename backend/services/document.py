import os
from datetime import date

from fpdf import FPDF
from fpdf.enums import XPos, YPos

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_COLOUR = "#1E4078"


def _hex_to_rgb(hex_colour: str) -> tuple[int, int, int]:
    hex_colour = hex_colour.lstrip("#")
    return int(hex_colour[0:2], 16), int(hex_colour[2:4], 16), int(hex_colour[4:6], 16)


def _resolve_logo_path(logo_url: str | None) -> str | None:
    if not logo_url:
        return None
    relative = logo_url.lstrip("/")
    full_path = os.path.join(_BACKEND_DIR, relative)
    return full_path if os.path.exists(full_path) else None


def _initials(name: str) -> str:
    parts = name.strip().split()
    return "".join(p[0].upper() for p in parts[:2])


def _make_pdf(subtitle: str, policy_number: str, tenant_name: str,
              primary_colour: str = _DEFAULT_COLOUR, logo_url: str = None):
    pdf = FPDF()
    pdf.compress = False
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Header ───────────────────────────────────────────────────────────────
    r, g, b = _hex_to_rgb(primary_colour or _DEFAULT_COLOUR)
    pdf.set_fill_color(r, g, b)
    pdf.rect(0, 0, 210, 28, style="F")

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(20, 8)
    pdf.cell(0, 10, tenant_name, new_x=XPos.RIGHT, new_y=YPos.TOP)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(20, 18)
    pdf.cell(0, 6, subtitle, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Logo — use tenant logo file if available, fall back to initials box
    logo_path = _resolve_logo_path(logo_url)
    if logo_path:
        try:
            pdf.image(logo_path, x=172, y=3, w=24, h=22)
        except Exception:
            logo_path = None
    if not logo_path:
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(174, 4, 20, 20, style="F")
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(r, g, b)
        pdf.set_xy(174, 10)
        pdf.cell(20, 8, _initials(tenant_name), align="C")

    pdf.set_text_color(0, 0, 0)
    pdf.set_y(32)

    # ── Policy reference bar ──────────────────────────────────────────────────
    pdf.set_fill_color(240, 244, 250)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(20)
    pdf.cell(170, 9, f"  Policy Number: {policy_number}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    def section_heading(title: str):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.set_x(20)
        pdf.cell(170, 7, f"  {title}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    def row(label: str, value: str):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_x(20)
        pdf.cell(55, 6, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(115, 6, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def footer():
        pdf.set_y(-30)
        pdf.set_draw_color(r, g, b)
        pdf.set_line_width(0.4)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(100, 100, 100)
        pdf.set_x(20)
        pdf.cell(
            0, 4,
            f"Generated: {date.today()}    |    {tenant_name} is authorised and regulated by the FCA.",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

    return pdf, section_heading, row, footer


def generate_policy_schedule(policy, tenant_name: str, primary_colour: str = None, logo_url: str = None, effective_premium=None) -> bytes:
    data = policy.current_data
    customer = data.get("customer", {})
    vehicle = data.get("vehicle", {})
    product_fields = data.get("product_fields") or {}

    address = customer.get("address") or {}
    address_str = ", ".join(
        p for p in [
            address.get("line1", ""),
            address.get("city", ""),
            address.get("postcode", ""),
        ] if p
    )

    # Use effective premium (sum of BIND + ENDORSEMENT deltas) if provided,
    # falling back to the original bind premium
    display_premium = effective_premium if effective_premium is not None else policy.premium

    pdf, section_heading, row, footer = _make_pdf("Policy Schedule", policy.policy_number, tenant_name, primary_colour, logo_url)

    section_heading("Cover Details")
    row("Product:", data.get("product", ""))
    row("Term:", f"{data.get('term_months', '')} months")
    row("Inception Date:", str(policy.inception_date))
    row("Expiry Date:", str(policy.expiry_date))
    row("Premium:", f"£{display_premium}")
    pdf.ln(4)

    section_heading("Insured Details")
    row("Name:", customer.get("name") or "-")
    row("Date of Birth:", customer.get("dob") or "-")
    row("Email:", customer.get("email") or "-")
    row("Address:", address_str or "-")
    pdf.ln(4)

    section_heading("Vehicle Details")
    row("Registration:", vehicle.get("registration") or "-")
    row("Make:", vehicle.get("make") or "-")
    row("Model:", vehicle.get("model") or "-")
    row("Year:", str(vehicle.get("year") or "-"))
    row("Purchase Price:", f"£{vehicle.get('purchase_price') or '-'}")
    row("Purchase Date:", vehicle.get("purchase_date") or "-")
    row("Finance Type:", vehicle.get("finance_type") or "-")
    pdf.ln(4)

    if product_fields:
        section_heading("Product Details")
        for key, value in product_fields.items():
            row(key.replace("_", " ").title() + ":", str(value))
        pdf.ln(4)

    # Fee Disclosure — FCA requires broker commission disclosure regardless of dealer presence
    broker_commission = policy.broker_commission or 0
    dealer_fee = policy.dealer_fee or 0
    net_to_insurer = display_premium - broker_commission
    total_payable = display_premium + dealer_fee

    section_heading("Fee Disclosure")
    dealer_info = data.get("dealer")
    if dealer_info:
        row("Dealer:", dealer_info.get("name", "-"))
        row("Dealer Fee:", f"£{dealer_fee:.2f}  (non-refundable, payable in addition to premium)")
    row("Broker Commission:", f"£{broker_commission:.2f}")
    row("Net Premium to Insurer:", f"£{net_to_insurer:.2f}")
    row("Total Payable:", f"£{total_payable:.2f}")
    pdf.ln(4)

    footer()
    return bytes(pdf.output())


def generate_cancellation_notice(policy, transaction, tenant_name: str, primary_colour: str = None, logo_url: str = None) -> bytes:
    data = transaction.data_after or {}
    cancellation_date = data.get("cancellation_date", str(date.today()))
    refund_amount = abs(float(transaction.premium_delta or 0))

    pdf, section_heading, row, footer = _make_pdf("Cancellation Notice", policy.policy_number, tenant_name, primary_colour, logo_url)

    section_heading("Cancellation Details")
    row("Effective Date:", cancellation_date)
    row("Original Inception:", str(policy.inception_date))
    row("Original Expiry:", str(policy.expiry_date))
    row("Pro-rata Refund:", f"£{refund_amount:.2f}")
    if transaction.reason_text:
        row("Reason:", transaction.reason_text)
    pdf.ln(4)

    section_heading("Refund Information")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(20)
    pdf.multi_cell(
        170, 6,
        f"A pro-rata refund of £{refund_amount:.2f} will be processed to your original payment method. "
        f"Please allow 5-10 working days for the refund to appear.",
    )
    pdf.ln(4)

    footer()
    return bytes(pdf.output())


def generate_reinstatement_notice(policy, transaction, tenant_name: str, primary_colour: str = None, logo_url: str = None) -> bytes:
    data = transaction.data_after or {}
    new_expiry = data.get("expiry_date", str(policy.expiry_date))
    reinstatement_date = data.get("reinstatement_date", str(date.today()))
    amount_due = float(transaction.premium_delta or 0)

    pdf, section_heading, row, footer = _make_pdf("Reinstatement Notice", policy.policy_number, tenant_name, primary_colour, logo_url)

    section_heading("Reinstatement Details")
    row("Reinstatement Date:", reinstatement_date)
    row("New Expiry Date:", new_expiry)
    row("Original Inception:", str(policy.inception_date))
    row("Amount Due:", f"£{amount_due:.2f}")
    pdf.ln(4)

    section_heading("Payment Information")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(20)
    pdf.multi_cell(
        170, 6,
        f"A reinstatement premium of £{amount_due:.2f} is due to reactivate your cover effective {reinstatement_date}. "
        f"Your policy will remain active until {new_expiry}. "
        f"Please ensure payment is made promptly to avoid any lapse in cover.",
    )
    pdf.ln(4)

    footer()
    return bytes(pdf.output())


def generate_finance_agreement(
    policy_number: str,
    customer_name: str,
    customer_address: str,
    vehicle_registration: str,
    finance_company_name: str,
    financed_amount: float,
    deposit: float,
    monthly_payment: float,
    finance_charge: float,
    total_repayable: float,
    apr: float,
    term_months: int,
) -> bytes:
    pdf = FPDF()
    pdf.compress = False
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)

    # Header
    pdf.set_fill_color(40, 40, 40)
    pdf.rect(0, 0, 210, 28, style="F")
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(20, 8)
    pdf.cell(0, 10, finance_company_name, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(20, 18)
    pdf.cell(0, 6, "Consumer Credit Agreement", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(32)

    # Agreement reference bar
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(20)
    pdf.cell(170, 9, f"  Agreement Reference: {policy_number}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    def section_heading(title: str):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(40, 40, 40)
        pdf.set_text_color(255, 255, 255)
        pdf.set_x(20)
        pdf.cell(170, 7, f"  {title}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    def row(label: str, value: str):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_x(20)
        pdf.cell(75, 6, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(95, 6, value, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Customer and vehicle details
    section_heading("Borrower Details")
    row("Full Name:", customer_name)
    row("Address:", customer_address)
    row("Vehicle Registration:", vehicle_registration)
    pdf.ln(4)

    # Key financial figures
    section_heading("Credit Details")
    row("Amount of Credit (Financed Amount):", f"£{financed_amount:.2f}")
    row("Deposit Paid:", f"£{deposit:.2f}")
    row("Total Charge for Credit:", f"£{finance_charge:.2f}")
    row("Total Amount Repayable:", f"£{total_repayable:.2f}")
    row("Representative APR:", f"{apr}%")
    row("Duration:", f"{term_months} months")
    pdf.ln(4)

    # Payment schedule table
    section_heading("Payment Schedule")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_x(20)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(20, 7, "No.", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(80, 7, "Description", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(35, 7, "Due Date", fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(35, 7, "Amount", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 9)
    fill = False
    pdf.set_fill_color(248, 248, 248)
    pdf.set_x(20)
    pdf.cell(20, 6, "-", fill=fill, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(80, 6, "Deposit (due on agreement)", fill=fill, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(35, 6, "On signing", fill=fill, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(35, 6, f"£{deposit:.2f}", fill=fill, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    for i in range(1, term_months + 1):
        fill = not fill
        pdf.set_x(20)
        pdf.cell(20, 6, str(i), fill=fill, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(80, 6, f"Monthly instalment {i}", fill=fill, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(35, 6, f"Month {i}", fill=fill, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(35, 6, f"£{monthly_payment:.2f}", fill=fill, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(4)

    # Cancellation rights
    section_heading("Your Right to Withdraw")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_x(20)
    pdf.multi_cell(
        170, 5,
        "You have the right to withdraw from this agreement without giving any reason within 14 days "
        "of the date of this agreement (the 'cooling-off period'). To exercise this right, you must notify "
        f"{finance_company_name} in writing before the end of the cooling-off period. If you withdraw, "
        "you must repay the credit advanced plus any interest accrued without delay and no later than "
        "30 calendar days after giving notice of withdrawal. This agreement is regulated by the "
        "Consumer Credit Act 1974.",
    )
    pdf.ln(4)

    # Footer
    pdf.set_y(-30)
    pdf.set_draw_color(40, 40, 40)
    pdf.set_line_width(0.4)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(20)
    pdf.cell(
        0, 4,
        f"Generated: {date.today()}    |    {finance_company_name} is authorised and regulated by the Financial Conduct Authority.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    return bytes(pdf.output())


def generate_endorsement_certificate(policy, transaction, tenant_name: str, primary_colour: str = None, logo_url: str = None) -> bytes:
    data_before = transaction.data_before or {}
    data_after = transaction.data_after or {}

    before_customer = data_before.get("customer", {})
    after_customer = data_after.get("customer", {})

    changes = []
    field_labels = {
        "name": "Customer Name",
        "email": "Customer Email",
        "address": "Customer Address",
    }
    for key, label in field_labels.items():
        before_val = before_customer.get(key)
        after_val = after_customer.get(key)
        if before_val != after_val:
            changes.append((label, str(before_val or "-"), str(after_val or "-")))

    pdf, section_heading, row, footer = _make_pdf("Endorsement Certificate", policy.policy_number, tenant_name, primary_colour, logo_url)

    section_heading("Endorsement Details")
    row("Effective Date:", str(date.today()))
    row("Premium Impact:", "No change")
    if transaction.reason_text:
        row("Reason:", transaction.reason_text)
    pdf.ln(4)

    section_heading("Changes Made")
    if changes:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_x(20)
        pdf.cell(55, 6, "Field", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(55, 6, "Previous Value", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(60, 6, "New Value", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.2)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(1)
        for label, before, after in changes:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_x(20)
            pdf.cell(55, 6, label, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(55, 6, before[:30], new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(60, 6, after[:30], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_x(20)
        pdf.cell(170, 6, "No recordable changes.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    footer()
    return bytes(pdf.output())
