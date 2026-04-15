from datetime import date

from fpdf import FPDF


def _initials(name: str) -> str:
    parts = name.strip().split()
    return "".join(p[0].upper() for p in parts[:2])


def generate_policy_schedule(policy, tenant_name: str) -> bytes:
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

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)

    # ── Header ───────────────────────────────────────────────────────────────
    pdf.set_fill_color(30, 64, 120)
    pdf.rect(0, 0, 210, 28, style="F")

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(20, 8)
    pdf.cell(0, 10, tenant_name, ln=False)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(20, 18)
    pdf.cell(0, 6, "Policy Schedule", ln=True)

    # Logo placeholder - white square with tenant initials top-right
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(174, 4, 20, 20, style="F")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 64, 120)
    pdf.set_xy(174, 10)
    pdf.cell(20, 8, _initials(tenant_name), align="C")

    pdf.set_text_color(0, 0, 0)
    pdf.set_y(32)

    # ── Policy reference bar ──────────────────────────────────────────────────
    pdf.set_fill_color(240, 244, 250)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(20)
    pdf.cell(170, 9, f"  Policy Number: {policy.policy_number}", fill=True, ln=True)
    pdf.ln(4)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def section_heading(title: str):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(30, 64, 120)
        pdf.set_text_color(255, 255, 255)
        pdf.set_x(20)
        pdf.cell(170, 7, f"  {title}", fill=True, ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    def row(label: str, value: str):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_x(20)
        pdf.cell(55, 6, label, ln=False)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(115, 6, value, ln=True)

    # ── Cover details ─────────────────────────────────────────────────────────
    section_heading("Cover Details")
    row("Product:", data.get("product", ""))
    row("Term:", f"{data.get('term_months', '')} months")
    row("Inception Date:", str(policy.inception_date))
    row("Expiry Date:", str(policy.expiry_date))
    row("Premium:", f"£{policy.premium}")
    pdf.ln(4)

    # ── Insured details ───────────────────────────────────────────────────────
    section_heading("Insured Details")
    row("Name:", customer.get("name") or "-")
    row("Date of Birth:", customer.get("dob") or "-")
    row("Email:", customer.get("email") or "-")
    row("Address:", address_str or "-")
    pdf.ln(4)

    # ── Vehicle details ───────────────────────────────────────────────────────
    section_heading("Vehicle Details")
    row("Registration:", vehicle.get("registration") or "-")
    row("Make:", vehicle.get("make") or "-")
    row("Model:", vehicle.get("model") or "-")
    row("Year:", str(vehicle.get("year") or "-"))
    row("Purchase Price:", f"£{vehicle.get('purchase_price') or '-'}")
    row("Purchase Date:", vehicle.get("purchase_date") or "-")
    row("Finance Type:", vehicle.get("finance_type") or "-")
    pdf.ln(4)

    # ── Product-specific fields ───────────────────────────────────────────────
    if product_fields:
        section_heading("Product Details")
        for key, value in product_fields.items():
            row(key.replace("_", " ").title() + ":", str(value))
        pdf.ln(4)

    # ── Footer ────────────────────────────────────────────────────────────────
    pdf.set_y(-30)
    pdf.set_draw_color(30, 64, 120)
    pdf.set_line_width(0.4)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(20)
    pdf.cell(
        0, 4,
        f"Generated: {date.today()}    |    {tenant_name} is authorised and regulated by the FCA.",
        ln=True,
    )

    return bytes(pdf.output())
