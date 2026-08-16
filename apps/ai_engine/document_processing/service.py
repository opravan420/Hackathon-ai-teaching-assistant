import os
from django.conf import settings
from .exceptions import (
    UnsupportedFileTypeError,
    DocumentExtractionError,
    NoExtractableTextError,
    InvalidDocumentError
)
from .pdf_parser import PDFParser
from .docx_parser import DOCXParser
from .pptx_parser import PPTXParser
from .txt_parser import TXTParser
from .validators import validate_uploaded_file
from apps.ai_engine.models import Document

def normalize_text(text: str) -> str:
    """
    Normalize text lines, normalize line endings, strip whitespaces,
    preserve paragraph splits, and prevent more than one consecutive blank line.
    """
    # Normalize carriage returns
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Process lines
    lines = [line.strip() for line in text.split('\n')]
    
    # Remove consecutive excessive blank lines
    cleaned_lines = []
    blank_count = 0
    for line in lines:
        if not line:
            blank_count += 1
            if blank_count <= 1:
                cleaned_lines.append('')
        else:
            blank_count = 0
            cleaned_lines.append(line)
            
    return '\n'.join(cleaned_lines).strip()

class DocumentService:
    """Service class for coordinating document verification and text extraction."""

    def __init__(self):
        self.parsers = {
            '.pdf': PDFParser(),
            '.docx': DOCXParser(),
            '.pptx': PPTXParser(),
            '.txt': TXTParser()
        }

    def process_document(self, teacher, uploaded_file) -> Document:
        """
        Validates, uploads, and parses text from a file, saving status logs in the database.
        
        Args:
            teacher: The Teacher user who owns the document.
            uploaded_file: The Django UploadedFile object.
            
        Returns:
            The created Document model instance.
        """
        # 1. Perform validation checks (file type, size limits, legacy formats)
        validate_uploaded_file(uploaded_file)

        _, ext = os.path.splitext(uploaded_file.name)
        ext = ext.lower()

        # 2. Store model instance initially as PENDING
        document = Document.objects.create(
            teacher=teacher,
            original_filename=uploaded_file.name,
            stored_file=uploaded_file,
            file_type=ext.lstrip('.').upper(),
            file_size=uploaded_file.size,
            extraction_status=Document.PENDING
        )

        # 3. Select parser and run extraction
        parser = self.parsers.get(ext)
        if not parser:
            document.extraction_status = Document.FAILED
            document.save()
            raise UnsupportedFileTypeError(f"Unsupported file type extension: {ext}")

        try:
            # Get absolute file path from the stored file
            file_path = document.stored_file.path
            raw_text = parser.extract_text(file_path)

            # 4. Clean and normalize extracted text
            normalized = normalize_text(raw_text)

            # 5. Update and finalize document status
            document.extracted_text = normalized
            document.character_count = len(normalized)
            document.extraction_status = Document.SUCCESS
            document.save()

        except NoExtractableTextError:
            document.extraction_status = Document.NO_EXTRACTABLE_TEXT
            document.save()
            raise
        except InvalidDocumentError as e:
            document.extraction_status = Document.FAILED
            document.save()
            raise
        except Exception as e:
            document.extraction_status = Document.FAILED
            document.save()
            raise DocumentExtractionError(f"Extraction failed: {str(e)}")

        return document

    def delete_document(self, document: Document):
        """
        Physically deletes stored file, removes document DB record,
        and rebuilds the teacher's FAISS index to purge deleted vectors.
        """
        teacher_id = document.teacher_id
        if document.stored_file and os.path.exists(document.stored_file.path):
            try:
                os.remove(document.stored_file.path)
            except Exception:
                pass
        document.delete()

        # Rebuild index for teacher to remove vectors of deleted document
        from apps.ai_engine.rag.retrieval_service import RetrievalService
        RetrievalService().rebuild_index_for_teacher(teacher_id)

