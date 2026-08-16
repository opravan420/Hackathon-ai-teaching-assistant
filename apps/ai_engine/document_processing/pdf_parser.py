import fitz  # PyMuPDF
from .base import BaseDocumentParser
from .exceptions import DocumentExtractionError, NoExtractableTextError, InvalidDocumentError

class PDFParser(BaseDocumentParser):
    """
    Parser for extracting text from PDF files using PyMuPDF.
    Supports selectable text extraction (Type A) and page rendering with OCR fallback for scanned PDFs (Type B).
    """

    def extract_text(self, file_path: str) -> str:
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise InvalidDocumentError(f"Corrupted or invalid PDF file: {str(e)}")

        try:
            # Path 1: Text-based PDF extraction
            extracted_pages = []
            for i, page in enumerate(doc, 1):
                text = page.get_text().strip()
                if text:
                    extracted_pages.append(f"[Page {i}]\n{text}")

            full_text = "\n\n".join(extracted_pages).strip()
            if full_text:
                doc.close()
                return full_text

            # Path 2: Scanned / Image-based PDF fallback (Page Rendering + OCR)
            ocr_pages = []
            try:
                import pytesseract
                from PIL import Image
                import io

                for i, page in enumerate(doc, 1):
                    pix = page.get_pixmap(dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = pytesseract.image_to_string(img).strip()
                    if ocr_text:
                        ocr_pages.append(f"[Page {i}]\n{ocr_text}")
            except (ImportError, Exception):
                pass

            doc.close()
            scanned_text = "\n\n".join(ocr_pages).strip()

            if not scanned_text:
                raise NoExtractableTextError(
                    "This PDF appears to be scanned/image-based and could not be processed. "
                    "Please provide a clear scan or text-based PDF."
                )

            return scanned_text

        except NoExtractableTextError:
            raise
        except Exception as e:
            raise DocumentExtractionError(f"Error extracting text from PDF: {str(e)}")
