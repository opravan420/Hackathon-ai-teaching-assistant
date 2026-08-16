import os
from .base import BaseDocumentParser
from .exceptions import DocumentExtractionError, NoExtractableTextError, InvalidDocumentError

class ImageParser(BaseDocumentParser):
    """
    Parser for extracting text from image files (PNG, JPG, JPEG).
    Uses PIL/Pillow strictly for image format validation & preprocessing,
    and delegates text extraction to the host OCR engine (e.g. pytesseract).
    """

    def extract_text(self, file_path: str) -> str:
        # Step 1: Preprocess and validate image using PIL
        try:
            from PIL import Image, ImageEnhance
            with Image.open(file_path) as img:
                img.verify()  # Validate image integrity
            
            # Reopen for preprocessing after verify()
            with Image.open(file_path) as img:
                # Convert to grayscale for cleaner OCR reading
                processed_img = img.convert('L')
                enhancer = ImageEnhance.Contrast(processed_img)
                processed_img = enhancer.enhance(1.5)
        except Exception as e:
            raise InvalidDocumentError(f"Corrupted or invalid image file: {str(e)}")

        # Step 2: Extract text using OCR engine (pytesseract)
        ocr_text = ""
        try:
            import pytesseract
            ocr_text = pytesseract.image_to_string(processed_img).strip()
        except (ImportError, Exception) as ocr_err:
            # Handle missing Tesseract binary or OCR execution error gracefully
            pass

        # Step 3: Fallback check using PyMuPDF if fitz has embed text layer
        if not ocr_text:
            try:
                import fitz
                doc = fitz.open(file_path)
                extracted = [page.get_text().strip() for page in doc if page.get_text().strip()]
                doc.close()
                if extracted:
                    ocr_text = "\n\n".join(extracted).strip()
            except Exception:
                pass

        if not ocr_text or len(ocr_text) == 0:
            raise NoExtractableTextError(
                "Unable to reliably read text from the uploaded answer sheet. "
                "Please upload a clearer image or digital document."
            )

        return ocr_text
