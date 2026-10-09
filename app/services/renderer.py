"""Certificate rendering: the renderer interface and the single predefined PDF template."""
import io
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas


@dataclass(frozen=True)
class CertificateData:
    """Everything printed on one certificate."""

    certificate_id: str
    recipient_name: str
    event_name: str
    issue_date: date
    issued_by: str = ""


class CertificateRenderer(Protocol):
    """Any renderer (PDF, PNG, HTML...) just needs to turn data into file bytes."""

    media_type: str
    file_extension: str

    def render(self, data: CertificateData) -> bytes: ...


# Template colours
NAVY = colors.HexColor("#1F3A5F")
GOLD = colors.HexColor("#C9A227")


class PdfCertificateRenderer:
    """The predefined certificate template, drawn with ReportLab on landscape A4."""

    media_type = "application/pdf"
    file_extension = "pdf"
    page_size = landscape(A4)

    def render(self, data: CertificateData) -> bytes:
        buffer = io.BytesIO()
        pdf = Canvas(buffer, pagesize=self.page_size)
        pdf.setTitle(f"Certificate - {data.recipient_name}")
        width, height = self.page_size
        center_x = width / 2

        self._draw_border(pdf, width, height)

        # Heading
        pdf.setFillColor(NAVY)
        pdf.setFont("Helvetica-Bold", 38)
        pdf.drawCentredString(center_x, height - 130, "CERTIFICATE")
        pdf.setFont("Helvetica", 16)
        pdf.drawCentredString(center_x, height - 158, "OF COMPLETION")

        # Body: recipient name and event (long text shrinks to fit)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Oblique", 15)
        pdf.drawCentredString(center_x, height - 215, "This is to certify that")

        max_text_width = width - 200
        self._draw_fitted(pdf, data.recipient_name, "Helvetica-Bold", 34, center_x, height - 265, max_text_width)
        pdf.setStrokeColor(GOLD)
        pdf.line(center_x - 200, height - 278, center_x + 200, height - 278)

        pdf.setFont("Helvetica-Oblique", 15)
        pdf.drawCentredString(center_x, height - 315, "has successfully completed")
        self._draw_fitted(pdf, data.event_name, "Helvetica-Bold", 22, center_x, height - 350, max_text_width)

        # Footer: date (left), issuer (right), unique ID (bottom) for verification
        pdf.setFont("Helvetica", 12)
        pdf.drawString(110, 120, f"Date: {data.issue_date.strftime('%d %B %Y')}")
        if data.issued_by:
            pdf.drawRightString(width - 110, 120, f"Issued by: {data.issued_by}")
        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(colors.grey)
        pdf.drawCentredString(center_x, 70, f"Certificate ID: {data.certificate_id}")

        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    @staticmethod
    def _draw_border(pdf: Canvas, width: float, height: float) -> None:
        pdf.setStrokeColor(NAVY)
        pdf.setLineWidth(6)
        pdf.rect(30, 30, width - 60, height - 60)
        pdf.setStrokeColor(GOLD)
        pdf.setLineWidth(2)
        pdf.rect(42, 42, width - 84, height - 84)

    @staticmethod
    def _draw_fitted(pdf: Canvas, text: str, font: str, max_size: int, x: float, y: float,
                     max_width: float, min_size: int = 12) -> None:
        """Draw centred text, shrinking the font until it fits max_width."""
        size = max_size
        while size > min_size and stringWidth(text, font, size) > max_width:
            size -= 1
        pdf.setFont(font, size)
        pdf.drawCentredString(x, y, text)
