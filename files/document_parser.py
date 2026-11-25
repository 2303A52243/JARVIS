"""Document parser for JARVIS.

Extracts plain text from common file formats so JARVIS can read and
summarize document contents without uploading them to external services.

Supported formats:
    .txt  – plain text
    .md   – markdown (returned as-is)
    .py / .js / .html / .css / .json – source / data files (plain text)
    .csv  – comma-separated values
    .pdf  – PDF via PyMuPDF (fitz)
    .docx – Word document via python-docx
    .xlsx – Excel via openpyxl (first sheet, cell values as text)
"""

from __future__ import annotations

from pathlib import Path

TEXT_EXTENSIONS = {".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".bat"}
CSV_EXTENSIONS  = {".csv"}
PDF_EXTENSIONS  = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
XLSX_EXTENSIONS = {".xlsx"}

ALL_SUPPORTED = TEXT_EXTENSIONS | CSV_EXTENSIONS | PDF_EXTENSIONS | DOCX_EXTENSIONS | XLSX_EXTENSIONS


def parse_document(path: str, max_chars: int = 20_000) -> str:
    """Extract and return text from the given document.

    Args:
        path:      Path to the file.
        max_chars: Maximum number of characters to return (truncated with a note).

    Returns:
        Extracted text as a string.

    Raises:
        ValueError: If the file format is not supported.
        FileNotFoundError: If the file does not exist.
    """
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = file_path.suffix.lower()

    if ext in TEXT_EXTENSIONS:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    elif ext in CSV_EXTENSIONS:
        text = _parse_csv(file_path)
    elif ext in PDF_EXTENSIONS:
        text = _parse_pdf(file_path)
    elif ext in DOCX_EXTENSIONS:
        text = _parse_docx(file_path)
    elif ext in XLSX_EXTENSIONS:
        text = _parse_xlsx(file_path)
    else:
        raise ValueError(f"Unsupported file format: '{ext}'. Supported: {sorted(ALL_SUPPORTED)}")

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n... [truncated – showing {max_chars} of {len(text)} characters]"

    return text


def _parse_csv(path: Path) -> str:
    import csv
    rows = []
    with path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(", ".join(row))
    return "\n".join(rows)


def _parse_pdf(path: Path) -> str:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n".join(pages)
    except ImportError:
        return f"[PDF parsing unavailable – install PyMuPDF: pip install pymupdf] File: {path}"
    except Exception as e:
        return f"[PDF parsing error: {e}] File: {path}"


def _parse_docx(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(path))
        return "\n".join(para.text for para in doc.paragraphs)
    except ImportError:
        return f"[DOCX parsing unavailable – install python-docx: pip install python-docx] File: {path}"
    except Exception as e:
        return f"[DOCX parsing error: {e}] File: {path}"


def _parse_xlsx(path: Path) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(path), data_only=True)
        sheet = wb.active
        rows = []
        for row in sheet.iter_rows(values_only=True):
            rows.append(", ".join("" if cell is None else str(cell) for cell in row))
        return "\n".join(rows)
    except ImportError:
        return f"[XLSX parsing unavailable – install openpyxl: pip install openpyxl] File: {path}"
    except Exception as e:
        return f"[XLSX parsing error: {e}] File: {path}"
