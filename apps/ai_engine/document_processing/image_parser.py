import fitz  # PyMuPDF
from .base import BaseDocumentParser
from .exceptions import DocumentExtractionError, NoExtractableTextError, InvalidDocumentError

class ImageParser(BaseDocumentParser):
    """Parser for extracting text from image files (PNG, JPG, JPEG) using PyMuPDF / OCR / PIL."""

    def extract_text(self, file_path: str) -> str:
        # Step 1: Try pytesseract if available on host system
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(file_path)
            ocr_text = pytesseract.image_to_string(img).strip()
            if ocr_text:
                return ocr_text
        except Exception:
            pass

        # Step 2: Try PyMuPDF (fitz) document extraction
        try:
            doc = fitz.open(file_path)
            extracted_pages = []
            for i, page in enumerate(doc, 1):
                text = page.get_text().strip()
                if text:
                    extracted_pages.append(text)
            doc.close()

            full_text = "\n\n".join(extracted_pages).strip()
            if full_text:
                return full_text
        except Exception as e:
            raise InvalidDocumentError(f"Corrupted or invalid image file: {str(e)}")

        # If no text could be extracted from image
        raise NoExtractableTextError("Could not extract readable text from image. Please ensure image contains clear digital/scanned text layer.")
