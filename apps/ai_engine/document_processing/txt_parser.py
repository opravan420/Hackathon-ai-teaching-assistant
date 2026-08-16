from .base import BaseDocumentParser
from .exceptions import DocumentExtractionError, NoExtractableTextError

class TXTParser(BaseDocumentParser):
    """Parser for extracting text from plain TXT files with encoding fallbacks."""

    def extract_text(self, file_path: str) -> str:
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        content = None

        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    content = f.read().strip()
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                raise DocumentExtractionError(f"Failed to read TXT file: {str(e)}")

        if content is None:
            raise DocumentExtractionError("Failed to decode TXT file with any common encoding.")

        if not content:
            raise NoExtractableTextError("TXT file is empty.")

        return content
