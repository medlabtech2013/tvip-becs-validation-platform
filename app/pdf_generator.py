import os
from io import BytesIO
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

import qrcode

def make_qr_png(data: str) -> BytesIO:
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

def build_validation_pdf(
    out_path: str,
    hospital_name: str,
    division_name: str,
    watermark_text: str,
    run: dict,
    verification_url: str,
    logo_path: str = "static/clinical_validation_lab_logo.png",
    badge_path = "static/badges/accreditation_badge.png"
) -> None:
    styles = getSampleStyleSheet()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=36, rightMargin=36, topMargin=28, bottomMargin=28)

    elements = []

    # Header (logo + titles)
    header_left = []
    if os.path.exists(logo_path):
        logo = Image(logo_path)
        logo._restrictSize(2.0 * inch, 1.0 * inch)
        header_left.append(logo)

    title = Paragraph(f"<b>{hospital_name}</b><br/>{division_name}<br/><b>BECS Validation Evidence Report</b>", styles["Title"])
    header_tbl = Table([[header_left if header_left else "", title]], colWidths=[2.2*inch, 8.0*inch])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    elements.append(header_tbl)
    elements.append(Spacer(1, 10))

    # Watermark-style banner (simple)
    elements.append(Paragraph(f"<font color='red'><b>{watermark_text}</b></font>", styles["Normal"]))
    elements.append(Spacer(1, 10))

    # Core table
    data = [
        ["Validation Run ID", run["run_id"]],
        ["Workflow", run["workflow"]],
        ["Test Script ID", run["test_script_id"]],
        ["Donor Type", run["donor_type"]],
        ["Recipient Type", run["recipient_type"]],
        ["Expected Result", run["expected_result"]],
        ["Actual Result", run["actual_result"]],
        ["Status", run["status"]],
        ["Risk Level / Score", f'{run["risk"]["level"]} / {run["risk"]["score"]}'],
        ["Risk Drivers", ", ".join(run["risk"]["drivers"]) if run["risk"]["drivers"] else "None"],
        ["Rule Trace", " | ".join(run["rule_trace"])],
        ["Timestamp (UTC)", run["timestamp_utc"]],
        ["Digital Evidence Hash (SHA-256)", run["evidence_hash"]],
    ]
    tbl = Table(data, colWidths=[2.3*inch, 8.2*inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.whitesmoke),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 14))

    # QR + verification
    qr_png = make_qr_png(verification_url)
    qr_img = Image(qr_png)
    qr_img._restrictSize(1.4*inch, 1.4*inch)

    verify_tbl = Table([
        [qr_img, Paragraph(f"<b>Verification</b><br/>{verification_url}", styles["Normal"])]
    ], colWidths=[1.6*inch, 8.9*inch])
    verify_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    elements.append(verify_tbl)

    doc.build(elements)

    # Write out
    with open(out_path, "wb") as f:
        f.write(buf.getvalue())
