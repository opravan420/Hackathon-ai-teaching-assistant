import re
from typing import List, Dict, Any, Optional
from django.conf import settings

class ChunkingService:
    """Service for splitting extracted document text into clean, contextual chunks."""

    def __init__(self, chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None):
        self.chunk_size = chunk_size or getattr(settings, 'RAG_CHUNK_SIZE', 1000)
        self.chunk_overlap = chunk_overlap or getattr(settings, 'RAG_CHUNK_OVERLAP', 200)

    def chunk_document(self, document) -> List[Dict[str, Any]]:
        text = document.extracted_text or ""
        return self.chunk_text(
            text=text,
            document_id=document.id,
            teacher_id=document.teacher_id,
            source_filename=document.original_filename
        )

    def chunk_text(self, text: str, document_id: int, teacher_id: int, source_filename: str) -> List[Dict[str, Any]]:
        if not text.strip():
            return []

        # Split into sections based on [Page X] or [Slide X] headers if present
        section_pattern = re.compile(r'\[(Page|Slide)\s+(\d+)\]', re.IGNORECASE)
        matches = list(section_pattern.finditer(text))

        sections = []
        if matches:
            for i, match in enumerate(matches):
                tag_type = match.group(1).capitalize()  # 'Page' or 'Slide'
                num = int(match.group(2))
                start_pos = match.end()
                end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                sec_text = text[start_pos:end_pos].strip()
                page_num = num if tag_type == 'Page' else None
                slide_num = num if tag_type == 'Slide' else None
                sections.append((sec_text, page_num, slide_num))
        else:
            sections.append((text.strip(), None, None))

        all_chunks = []
        global_chunk_idx = 0

        for sec_text, page_num, slide_num in sections:
            if not sec_text:
                continue
            
            raw_chunks = self._split_text_into_chunks(sec_text)
            for c_text in raw_chunks:
                if c_text.strip():
                    all_chunks.append({
                        'chunk_text': c_text.strip(),
                        'document_id': document_id,
                        'teacher_id': str(teacher_id),
                        'chunk_index': global_chunk_idx,
                        'source_filename': source_filename,
                        'page_number': page_num,
                        'slide_number': slide_num,
                    })
                    global_chunk_idx += 1

        return all_chunks

    def _split_text_into_chunks(self, text: str) -> List[str]:
        if len(text) <= self.chunk_size:
            return [text]

        # Break text into paragraphs first
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        units = []
        for p in paragraphs:
            if len(p) <= self.chunk_size:
                units.append(p)
            else:
                # Break paragraph into sentences (respecting Hindi purna viram '|' / '।' and English '.')
                sentences = re.split(r'(?<=[.!?।\n])\s+', p)
                for s in sentences:
                    s = s.strip()
                    if not s:
                        continue
                    if len(s) <= self.chunk_size:
                        units.append(s)
                    else:
                        # Hard break if a single sentence exceeds chunk size
                        step = self.chunk_size - self.chunk_overlap if self.chunk_size > self.chunk_overlap else self.chunk_size
                        for k in range(0, len(s), step):
                            units.append(s[k:k + self.chunk_size])

        # Group units into chunks with overlap
        chunks = []
        current_chunk = ""

        for unit in units:
            if not current_chunk:
                current_chunk = unit
            elif len(current_chunk) + 1 + len(unit) <= self.chunk_size:
                current_chunk += "\n\n" + unit
            else:
                chunks.append(current_chunk)
                if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                    overlap_text = current_chunk[-self.chunk_overlap:]
                    current_chunk = overlap_text + "\n\n" + unit
                else:
                    current_chunk = unit

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
