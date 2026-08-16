class DocumentError(Exception):
    """Base exception for all document processing errors."""
    pass

class UnsupportedFileTypeError(DocumentError):
    """Raised when file extension or MIME type is not supported."""
    pass

class FileSizeLimitError(DocumentError):
    """Raised when file size exceeds the allowed limit."""
    pass

class InvalidDocumentError(DocumentError):
    """Raised when document is corrupted or invalid."""
    pass

class DocumentExtractionError(DocumentError):
    """Raised when parser fails to read document."""
    pass

class NoExtractableTextError(DocumentError):
    """Raised when document contains no extractable text (e.g. scanned image PDF)."""
    pass
