"""Extract plain text from PDF bytes using pdfplumber."""
from __future__ import annotations

import io
import logging

log = logging.getLogger(__name__)


class PDFExtractionError(RuntimeError):
    """Raised when a PDF cannot be read (encrypted, corrupt, empty)."""


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Return all text from the PDF, pages joined with form-feed.

    Raises PDFExtractionError for encrypted, corrupt or empty files.
    """
    try:
        import pdfplumber  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("pdfplumber is not installed. Run: pip install pdfplumber") from exc

    if not pdf_bytes or len(pdf_bytes) < 20:
        raise PDFExtractionError("PDF dosyası boş veya çok kısa.")

    try:
        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                raise PDFExtractionError("PDF sayfası yok (0 sayfa).")
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
        return "\f".join(pages)
    except PDFExtractionError:
        raise
    except Exception as exc:
        log.warning("pdf_extraction_failed reason=%s", exc)
        raise PDFExtractionError(f"PDF okunamadı: {exc}") from exc
