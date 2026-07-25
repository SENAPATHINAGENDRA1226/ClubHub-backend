import os
import uuid
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas


def generate_certificate_pdf(
    certificate_id: uuid.UUID,
    student_name: str,
    event_title: str,
    certificate_type: str,
    issued_at: datetime,
) -> str:
    media_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media", "certificates")
    os.makedirs(media_dir, exist_ok=True)

    filename = f"{certificate_id}.pdf"
    file_path = os.path.join(media_dir, filename)

    c = canvas.Canvas(file_path, pagesize=landscape(letter))
    width, height = landscape(letter)

    # Decorative Border
    c.setStrokeColor(colors.HexColor("#0ea5e9"))
    c.setLineWidth(5)
    c.rect(20, 20, width - 40, height - 40)

    c.setStrokeColor(colors.HexColor("#0284c7"))
    c.setLineWidth(1.5)
    c.rect(25, 25, width - 50, height - 50)

    # Title Header
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawCentredString(width / 2, height - 100, "CERTIFICATE OF ACHIEVEMENT")

    c.setFont("Helvetica-Oblique", 14)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawCentredString(width / 2, height - 130, "ClubHub Campus Community")

    # Recipient
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawCentredString(width / 2, height - 190, "This is proudly presented to")

    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor("#0284c7"))
    c.drawCentredString(width / 2, height - 235, student_name)

    # Event & Type
    cert_type_str = certificate_type.replace("_", " ").upper()
    c.setFont("Helvetica", 14)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawCentredString(width / 2, height - 280, f"for outstanding participation as {cert_type_str} in")

    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.HexColor("#0f172a"))
    c.drawCentredString(width / 2, height - 315, f'"{event_title}"')

    # Date & Verification ID
    date_str = issued_at.strftime("%B %d, %Y")
    c.setFont("Helvetica", 11)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawString(60, 60, f"Issued Date: {date_str}")
    c.drawRightString(width - 60, 60, f"Certificate ID: {certificate_id}")

    c.save()

    return f"/media/certificates/{filename}"
