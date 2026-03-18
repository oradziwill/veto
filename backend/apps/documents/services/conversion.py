"""
Convert uploaded documents (PDF, images) to HTML.
PDF: PyMuPDF text extraction; if minimal text, render pages to images and use OpenAI vision for OCR.
"""

from __future__ import annotations

import base64
import html
import logging
from pathlib import Path

import fitz
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH = 50  # Below this we use OCR for PDF


def _text_to_simple_html(raw: str) -> str:
    """Turn plain text into minimal HTML (paragraphs)."""
    if not raw or not raw.strip():
        return "<html><body><p></p></body></html>"
    parts = [p.strip() for p in raw.strip().split("\n\n") if p.strip()]
    paragraphs = [f"<p>{html.escape(p)}</p>" for p in parts]
    if not paragraphs:
        paragraphs = [f"<p>{html.escape(raw.strip())}</p>"]
    return "<html><body>\n" + "\n".join(paragraphs) + "\n</body></html>"


def _ocr_image_with_openai(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Send a single image to OpenAI vision and return extracted text."""
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set; cannot run OCR.")
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_uri = f"data:{mime_type};base64,{b64}"
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract all text from this image exactly as it appears. Preserve line breaks and structure. If there is no text, respond with a single empty line.",
                    },
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
        max_tokens=4096,
    )
    return (response.choices[0].message.content or "").strip()


def convert_pdf_to_html(pdf_bytes: bytes) -> str:
    """
    Convert PDF to HTML. Uses PyMuPDF text extraction; if very little text,
    renders each page to an image and uses OpenAI vision for OCR.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        full_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            full_text.append(text)
        combined = "\n\n".join(full_text)
        if len(combined.strip()) >= MIN_TEXT_LENGTH:
            return _text_to_simple_html(combined)
        # Minimal text: use OCR per page
        logger.info("PDF has minimal text, using OpenAI vision OCR for %s page(s)", len(doc))
        ocr_parts = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=150, alpha=False)
            img_bytes = pix.tobytes("png")
            part = _ocr_image_with_openai(img_bytes, "image/png")
            if part:
                ocr_parts.append(part)
        combined = "\n\n".join(ocr_parts)
        return _text_to_simple_html(combined or "(No text extracted)")
    finally:
        doc.close()


def convert_image_to_html(image_bytes: bytes, content_type: str) -> str:
    """Convert a single image to HTML by OCR."""
    mime = content_type or "image/png"
    text = _ocr_image_with_openai(image_bytes, mime)
    return _text_to_simple_html(text or "(No text extracted)")


def convert_document_to_html(data: bytes, content_type: str, original_filename: str) -> str:
    """
    Dispatch by content type. Returns HTML string.
    Supports: application/pdf, image/jpeg, image/png, image/gif, image/webp.
    """
    ct = (content_type or "").lower().strip()
    if ct == "application/pdf":
        return convert_pdf_to_html(data)
    if ct in ("image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"):
        return convert_image_to_html(data, ct)
    # Fallback by extension
    ext = (Path(original_filename or "").suffix or "").lower()
    if ext == ".pdf":
        return convert_pdf_to_html(data)
    if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        return convert_image_to_html(data, ct or "image/png")
    raise ValueError(f"Unsupported document type: {content_type!r} / {original_filename!r}")
