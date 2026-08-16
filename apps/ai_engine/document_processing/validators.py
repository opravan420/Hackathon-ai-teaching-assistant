import os
from .exceptions import UnsupportedFileTypeError, FileSizeLimitError

def validate_uploaded_file(file):
    """
    Validate the uploaded file properties.
    Ensures extension is supported and size limits are respected.
    Specifically rejects legacy .ppt files.
    """
    name, ext = os.path.splitext(file.name)
    ext = ext.lower()

    if ext == '.ppt':
        raise UnsupportedFileTypeError("legacy .ppt format is not supported. Please upload a .pptx file instead.")

    allowed_extensions = ['.pdf', '.docx', '.pptx', '.txt']
    if ext not in allowed_extensions:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{ext}'. Supported formats: PDF, DOCX, PPTX, TXT."
        )

    # Validate file size
    max_size_mb = int(os.getenv('MAX_DOCUMENT_SIZE_MB', 25))
    size_mb = file.size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise FileSizeLimitError(
            f"File size ({size_mb:.2f} MB) exceeds maximum allowed size of {max_size_mb} MB."
        )
