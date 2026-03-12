"""Extract plain text from PDF bytes using pdfplumber."""
from __future__ import annotations

import io


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Return all text from the PDF, pages joined with newlines."""
    try:
        import pdfplumber  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("pdfplumber is not installed. Run: pip install pdfplumber") from exc

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)
    return "\n".join(pages)
