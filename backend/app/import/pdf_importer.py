import logging
import os
from pathlib import Path
from typing import List, Dict, Any, Callable

from .manager import register_importer, import_records

logger = logging.getLogger(__name__)


def _extract_text(pdf_path: str) -> str:
    """Deterministically extract text from a PDF.
    Uses PyPDF2 if available; otherwise returns an empty string and logs.
    ponytail: no external CLI tools, minimal dependency.
    """
    try:
        import PyPDF2  # type: ignore
    except ImportError:
        logger.warning("PyPDF2 not installed – PDF text extraction skipped for %s", pdf_path)
        return ""
    try:
        reader = PyPDF2.PdfReader(pdf_path)
        text = []
        for page in reader.pages:
            text.append(page.extract_text() or "")
        return "\n\n".join(text)
    except Exception:
        logger.exception("Failed to extract PDF text from %s", pdf_path)
        return ""


def _load_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Create a single record for a PDF file.
    Includes metadata: filename, size, modification time, page count (if available).
    Content is deterministic text extraction when possible.
    """
    p = Path(pdf_path)
    if not p.is_file():
        logger.error("PDF file not found: %s", pdf_path)
        return []
    stat = p.stat()
    text = _extract_text(pdf_path)
    payload: Dict[str, Any] = {
        "file_name": p.name,
        "file_path": str(p),
        "size_bytes": stat.st_size,
        "modified_ts": stat.st_mtime,
        "content": text,
    }
    # page count via PyPDF2 if possible
    try:
        import PyPDF2  # type: ignore
        reader = PyPDF2.PdfReader(pdf_path)
        payload["page_count"] = len(reader.pages)
    except Exception:
        pass
    # external_id based on file path hash
    payload["external_id"] = f"pdf:{p.resolve()}"
    return [payload]


async def import_pdf(pdf_path: str, progress_callback: Callable[[int], None] | None = None) -> int:
    """Import a PDF as a historical observation.
    Returns number of new events (0 or 1).
    """
    records = _load_pdf(pdf_path)
    if not records:
        return 0
    if progress_callback:
        progress_callback(len(records))
    created = await import_records("pdf_import", records)
    logger.info("Imported %d new PDF observation from %s", created, pdf_path)
    return created

# Register importer
register_importer("pdf_import", "1.0", lambda rec: rec)  # ponytail: identity handler
