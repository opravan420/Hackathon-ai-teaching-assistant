import fitz  # PyMuPDF
from .base import BaseDocumentParser
from .exceptions import DocumentExtractionError, NoExtractableTextError, InvalidDocumentError

class PDFParser(BaseDocumentParser):
    """Parser for extracting text from PDF files using PyMuPDF."""

    def extract_text(self, file_path: str) -> str:
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise InvalidDocumentError(f"Corrupted or invalid PDF file: {str(e)}")

        try:
            extracted_pages = []
            for i, page in enumerate(doc, 1):
                text = page.get_text().strip()
                if text:
                    extracted_pages.append(f"[Page {i}]\n{text}")
            doc.close()

            full_text = "\n\n".join(extracted_pages).strip()
            if not full_text:
                raise NoExtractableTextError("NO_EXTRACTABLE_TEXT")

            return full_text
        except NoExtractableTextError:
            raise
        except Exception as e:
            raise DocumentExtractionError(f"Error extracting text from PDF: {str(e)}")
