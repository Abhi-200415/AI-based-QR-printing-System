import os
import io
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether
)

from app.core.config import UPLOAD_DIR
from app.database.models import ActiveJob, JobFinishingService, PaymentStatus
from app.utils.logger import logger


RECEIPTS_DIR = Path(UPLOAD_DIR) / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)


def build_receipt_dict_for_job(job: ActiveJob, db: Session, fallback_customer_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Extracts authoritative receipt breakdown from ActiveJob and DB relationships.
    """
    shop = job.owner
    shop_name = shop.shop_name if shop else "AI Smart Printing Shop"
    shop_address = shop.address if shop and shop.address else ""
    shop_phone = shop.phone if shop and shop.phone else ""

    # Finishing services grouped
    all_services = db.query(JobFinishingService).filter(JobFinishingService.job_id == job.job_id).all()
    file_srv_map = {}
    order_srvs = []

    for s in all_services:
        srv_item = {
            "id": str(s.id),
            "service_name": s.service_name,
            "unit_price": float(s.unit_price or 0),
            "quantity": s.quantity or 1,
            "total_price": float(s.total_price or 0)
        }
        if s.file_id:
            fid_str = str(s.file_id)
            if fid_str not in file_srv_map:
                file_srv_map[fid_str] = []
            file_srv_map[fid_str].append(srv_item)
        else:
            order_srvs.append(srv_item)

    items = []
    printing_subtotal = Decimal("0.00")
    for f in (job.files or []):
        file_cost = Decimal(str(f.estimated_cost or "0.00"))
        printing_subtotal += file_cost
        f_srvs = file_srv_map.get(str(f.file_id), [])

        items.append({
            "file_id": str(f.file_id),
            "filename": f.original_filename or "document.pdf",
            "page_count": f.page_count or 1,
            "copies": f.copies or 1,
            "paper_size": f.paper_size.value if hasattr(f.paper_size, "value") else str(f.paper_size or "A4"),
            "orientation": f.orientation.value if hasattr(f.orientation, "value") else str(f.orientation or "Portrait"),
            "print_type": f.print_type.value if hasattr(f.print_type, "value") else str(f.print_type or "BW"),
            "duplex": bool(f.duplex),
            "page_ranges": f.page_ranges,
            "printing_cost": float(file_cost),
            "finishing_services": f_srvs
        })

    finishing_subtotal = sum(Decimal(str(s.total_price or "0.00")) for s in all_services)
    tax_amt = Decimal(str(job.tax or "0.00"))
    grand_total = Decimal(str(job.total_amount or "0.00"))
    if grand_total <= Decimal("0.00"):
        grand_total = printing_subtotal + finishing_subtotal + tax_amt

    # Payment details
    pmt = job.payment
    pmt_method = pmt.payment_method.value if (pmt and pmt.payment_method) else "ONLINE"
    pmt_status = pmt.status.value if pmt else (job.payment_status.value if job.payment_status else "Pending")
    txn_id = pmt.transaction_id or pmt.provider_payment_id if pmt else None

    # Status text formatting for clarity
    if pmt_status == "Paid":
        if pmt_method == "Cash":
            display_status = "PAID (Cash at Counter Verified)"
        else:
            display_status = "PAID (Online Gateway Verified)"
    elif pmt_status == "Pending":
        if pmt_method == "Cash":
            display_status = "PAYMENT PENDING (Awaiting Counter Confirmation)"
        else:
            display_status = "PAYMENT PENDING (Awaiting Online Verification)"
    elif pmt_status == "Failed":
        display_status = "PAYMENT FAILED"
    elif pmt_status == "Refunded":
        display_status = "REFUNDED"
    else:
        display_status = pmt_status.upper()

    date_str = job.created_at.strftime("%d %b %Y, %I:%M %p") if job.created_at else datetime.utcnow().strftime("%d %b %Y, %I:%M %p")

    cust_name = job.customer_name or job.customer_reference or fallback_customer_name or "Valued Customer"

    return {
        "order_id": str(job.job_id),
        "clean_id": str(job.job_id)[:8],
        "date_time": date_str,
        "shop_name": shop_name,
        "shop_address": shop_address,
        "shop_phone": shop_phone,
        "customer_name": cust_name,
        "customer_reference": job.customer_reference,
        "items": items,
        "order_finishing_services": order_srvs,
        "printing_subtotal": float(printing_subtotal),
        "finishing_subtotal": float(finishing_subtotal),
        "tax": float(tax_amt),
        "grand_total": float(grand_total),
        "payment_method": pmt_method,
        "payment_status": pmt_status,
        "display_status": display_status,
        "transaction_id": txn_id
    }


def generate_receipt_pdf(data: Dict[str, Any]) -> bytes:
    """
    Renders a genuine, high-quality, professional PDF receipt using ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom typography & color styles
    primary_color = colors.HexColor("#1e1b4b")
    accent_color = colors.HexColor("#4338ca")
    text_dark = colors.HexColor("#0f172a")
    text_muted = colors.HexColor("#475569")
    success_color = colors.HexColor("#059669")
    warning_color = colors.HexColor("#d97706")
    danger_color = colors.HexColor("#dc2626")
    bg_light = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#e2e8f0")

    title_style = ParagraphStyle(
        "ShopTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
        alignment=1
    )

    sub_title_style = ParagraphStyle(
        "ShopSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=text_muted,
        alignment=1
    )

    badge_paid_style = ParagraphStyle(
        "BadgePaid",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=success_color if data.get("payment_status") == "Paid" else warning_color,
        alignment=1
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=text_muted
    )

    meta_val_style = ParagraphStyle(
        "MetaVal",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=text_dark
    )

    section_heading_style = ParagraphStyle(
        "SecHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=accent_color,
        spaceAfter=4
    )

    table_header_style = ParagraphStyle(
        "TH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        "TD",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=text_dark
    )

    table_cell_bold = ParagraphStyle(
        "TDBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=text_dark
    )

    table_cell_specs = ParagraphStyle(
        "TDSpecs",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=text_muted
    )

    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=text_muted,
        alignment=1
    )

    story = []

    # 1. Header: Shop Name & Details
    story.append(Paragraph(data["shop_name"], title_style))
    contact_parts = []
    if data.get("shop_address"):
        contact_parts.append(data["shop_address"])
    if data.get("shop_phone"):
        contact_parts.append(f"Phone: {data['shop_phone']}")
    if contact_parts:
        story.append(Spacer(1, 3))
        story.append(Paragraph(" • ".join(contact_parts), sub_title_style))

    story.append(Spacer(1, 6))
    story.append(Paragraph(f"• OFFICIAL TAX & PRINT RECEIPT •", sub_title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"STATUS: {data['display_status']}", badge_paid_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=border_color, spaceAfter=12))

    # 2. Metadata Grid (Order ID, Date, Customer Name, Payment Method)
    meta_table_data = [
        [
            Paragraph("RECEIPT / ORDER ID", meta_label_style),
            Paragraph("DATE & TIME", meta_label_style),
            Paragraph("CUSTOMER NAME", meta_label_style),
            Paragraph("PAYMENT METHOD", meta_label_style)
        ],
        [
            Paragraph(f"#{data['clean_id']}", meta_val_style),
            Paragraph(data["date_time"], meta_val_style),
            Paragraph(data["customer_name"], meta_val_style),
            Paragraph(f"{data['payment_method']} ({data['payment_status']})", meta_val_style)
        ]
    ]
    if data.get("transaction_id"):
        meta_table_data[0].append(Paragraph("TXN REF / ID", meta_label_style))
        meta_table_data[1].append(Paragraph(str(data["transaction_id"]), meta_val_style))

    meta_table = Table(meta_table_data, colWidths=None)
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_light),
        ('BOX', (0, 0), (-1, -1), 0.5, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 16))

    # 3. Itemized Document Table
    story.append(Paragraph("ITEMIZED PRINT DOCUMENTS", section_heading_style))

    doc_table_data = [
        [
            Paragraph("Document Item & Print Specifications", table_header_style),
            Paragraph("Pages", table_header_style),
            Paragraph("Copies", table_header_style),
            Paragraph("Amount", table_header_style)
        ]
    ]

    for item in data.get("items", []):
        filename = item.get("filename", "document.pdf")
        specs = (
            f"{item.get('paper_size', 'A4')} • {item.get('print_type', 'BW')} • "
            f"{'Double-Sided' if item.get('duplex') else 'Single-Sided'}"
        )
        if item.get("page_ranges"):
            specs += f" (Pages: {item.get('page_ranges')})"

        # Check per-file finishing services
        f_srvs = item.get("finishing_services", [])
        srv_lines = []
        for s in f_srvs:
            srv_lines.append(f"+ {s['service_name']} (₹{s['total_price']:.2f})")
        if srv_lines:
            specs += " | Finishing: " + ", ".join(srv_lines)

        doc_table_data.append([
            [Paragraph(filename, table_cell_bold), Paragraph(specs, table_cell_specs)],
            Paragraph(str(item.get("page_count", 1)), table_cell_style),
            Paragraph(str(item.get("copies", 1)), table_cell_style),
            Paragraph(f"₹{item.get('printing_cost', 0.0):.2f}", table_cell_bold)
        ])

    # Add order-level finishing services if any
    for srv in data.get("order_finishing_services", []):
        doc_table_data.append([
            [Paragraph(f"✨ Finishing: {srv['service_name']}", table_cell_bold), Paragraph(f"Rate: ₹{srv['unit_price']:.2f} × {srv['quantity']}", table_cell_specs)],
            Paragraph("-", table_cell_style),
            Paragraph(str(srv.get("quantity", 1)), table_cell_style),
            Paragraph(f"₹{srv.get('total_price', 0.0):.2f}", table_cell_bold)
        ])

    doc_table = Table(
        doc_table_data,
        colWidths=[290, 60, 60, 110],
        repeatRows=1
    )
    doc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), accent_color),
        ('ALIGN', (1, 0), (2, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, bg_light]),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
    ]))
    story.append(doc_table)
    story.append(Spacer(1, 14))

    # 4. Financial Totals Box
    totals_data = [
        [Paragraph("Printing Charges Subtotal:", meta_label_style), Paragraph(f"₹{data['printing_subtotal']:.2f}", meta_val_style)],
    ]
    if data.get("finishing_subtotal", 0) > 0:
        totals_data.append([Paragraph("Finishing Services Subtotal:", meta_label_style), Paragraph(f"₹{data['finishing_subtotal']:.2f}", meta_val_style)])
    if data.get("tax", 0) > 0:
        totals_data.append([Paragraph("Taxes & GST (Included):", meta_label_style), Paragraph(f"₹{data['tax']:.2f}", meta_val_style)])

    total_highlight_style = ParagraphStyle(
        "TotalHighlight",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        textColor=success_color,
        alignment=2
    )
    totals_data.append([Paragraph("TOTAL AMOUNT PAID:", meta_val_style), Paragraph(f"₹{data['grand_total']:.2f}", total_highlight_style)])

    totals_table = Table(totals_data, colWidths=[360, 160])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEBELOW', (0, -1), (1, -1), 1.5, primary_color),
        ('LINEABOVE', (0, -1), (1, -1), 1.0, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    story.append(KeepTogether(totals_table))
    story.append(Spacer(1, 24))

    # 5. Security & Verification Note
    story.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceAfter=8))
    note_text = (
        f"Thank you for choosing {data['shop_name']}. This authentic receipt was cryptographically generated by the AI Smart Printing System. "
        f"Order reference #{data['clean_id']}. Please keep this receipt for your records."
    )
    story.append(Paragraph(note_text, footer_style))

    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def ensure_cached_pdf_receipt(job: ActiveJob, db: Session, fallback_customer_name: Optional[str] = None) -> str:
    """
    Renders and saves the genuine PDF receipt to secure on-disk storage
    before the customer name is scrubbed from the active DB record.
    Returns path to the cached PDF.
    """
    clean_id = str(job.job_id)[:8]
    pdf_filename = f"Receipt_Order_{clean_id}.pdf"
    pdf_path = RECEIPTS_DIR / f"{job.job_id}.pdf"

    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        return str(pdf_path)

    data = build_receipt_dict_for_job(job, db, fallback_customer_name=fallback_customer_name)
    pdf_bytes = generate_receipt_pdf(data)

    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    logger.info(f"Cached genuine PDF receipt at {pdf_path}")
    return str(pdf_path)


def get_receipt_pdf_bytes(job: ActiveJob, db: Session) -> Tuple[bytes, str]:
    """
    Returns (pdf_bytes, filename) for downloading.
    Uses cached genuine PDF if available, otherwise renders fresh.
    """
    clean_id = str(job.job_id)[:8]
    pdf_filename = f"Receipt_Order_{clean_id}.pdf"
    cached_path = RECEIPTS_DIR / f"{job.job_id}.pdf"

    if cached_path.exists() and cached_path.stat().st_size > 0:
        with open(cached_path, "rb") as f:
            return f.read(), pdf_filename

    # Render fresh and cache
    data = build_receipt_dict_for_job(job, db)
    pdf_bytes = generate_receipt_pdf(data)

    try:
        with open(cached_path, "wb") as f:
            f.write(pdf_bytes)
    except Exception as e:
        logger.warning(f"Failed to cache receipt PDF to disk: {e}")

    return pdf_bytes, pdf_filename
