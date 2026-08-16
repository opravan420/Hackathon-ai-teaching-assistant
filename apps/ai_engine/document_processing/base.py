class BaseDocumentParser:
    """Interface for document text extraction parsers."""
    
    def extract_text(self, file_path: str) -> str:
        """
        Extract raw text content from the file.
        
        Args:
            file_path: Absolute path to the file on disk.
            
        Returns:
            The raw extracted text string.
        """
        raise NotImplementedError("Subclasses must implement extract_text method.")
