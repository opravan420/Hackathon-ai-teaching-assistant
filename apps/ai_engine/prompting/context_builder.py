from typing import List, Dict, Any, Optional

class ContextBuilder:
    """Formats retrieved document chunks into clean structured context for LLM prompts."""

    def build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Builds a formatted string from a list of chunk dictionaries.
        Omits similarity scores from model context string while preserving source filename,
        page number, and slide number headers.
        """
        if not chunks:
            return ""

        context_blocks = []
        for idx, chunk in enumerate(chunks, 1):
            source_filename = chunk.get('source_filename', 'Unknown Document')
            page_number = chunk.get('page_number')
            slide_number = chunk.get('slide_number')
            text = chunk.get('chunk_text', '').strip()

            header_parts = [f"SOURCE: {source_filename}"]
            if page_number is not None:
                header_parts.append(f"PAGE: {page_number}")
            if slide_number is not None:
                header_parts.append(f"SLIDE: {slide_number}")

            header = " | ".join(header_parts)
            block = f"--- CHUNK {idx} [{header}] ---\n{text}"
            context_blocks.append(block)

        return "\n\n".join(context_blocks)
