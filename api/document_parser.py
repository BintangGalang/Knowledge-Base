import io
import os

def parse_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using pypdf with pymupdf fallback"""
    text_parts = []
    
    # 1. Try pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(page_text.strip())
    except Exception as e:
        print(f"[Parser Warning] pypdf failed: {e}")

    # 2. Fallback to fitz (PyMuPDF) if text extracted is empty or pypdf failed
    if not text_parts:
        try:
            import fitz
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            for page in doc:
                page_text = page.get_text()
                if page_text and page_text.strip():
                    text_parts.append(page_text.strip())
        except Exception as e:
            print(f"[Parser Warning] PyMuPDF failed: {e}")

    full_text = "\n\n".join(text_parts).strip()
    if not full_text:
        raise ValueError("Gagal mengurai teks dari file PDF (file mungkin berupa scanned image tanpa OCR)")
    return full_text


def parse_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX file using python-docx"""
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = []
        for p in doc.paragraphs:
            if p.text.strip():
                paragraphs.append(p.text.strip())
        
        # Also extract table text if present
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)

        full_text = "\n\n".join(paragraphs).strip()
        if not full_text:
            raise ValueError("File Word/DOCX kosong atau tidak memiliki teks yang valid")
        return full_text
    except Exception as e:
        raise ValueError(f"Gagal mengurai file Word/DOCX: {str(e)}")


def parse_text(file_bytes: bytes) -> str:
    """Decode plain text or markdown content"""
    for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            return file_bytes.decode(enc).strip()
        except Exception:
            continue
    raise ValueError("Gagal menguraikan encoding file teks")


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    """Dispatch file parsing based on filename extension"""
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == ".pdf":
        return parse_pdf(file_bytes)
    elif ext in [".docx", ".doc"]:
        return parse_docx(file_bytes)
    elif ext in [".txt", ".md", ".json", ".csv", ".log"]:
        return parse_text(file_bytes)
    else:
        # Default try parsing as plain text
        try:
            return parse_text(file_bytes)
        except Exception:
            raise ValueError(f"Format file '{ext}' tidak didukung. Harap gunakan .pdf, .docx, .doc, .txt, atau .md")
