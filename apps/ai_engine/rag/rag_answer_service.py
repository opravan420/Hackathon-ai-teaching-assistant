import logging
from typing import List, Dict, Any
from apps.ai_engine.rag.retrieval_service import RetrievalService
from apps.ai_engine.prompting.context_builder import ContextBuilder
from apps.ai_engine.prompting.prompt_builder import PromptBuilder
from apps.ai_engine.services.llm_service import LLMService
from apps.ai_engine.exceptions import (
    LLMConnectionError,
    LLMTimeoutError,
    LLMInvalidModelError,
    LLMResponseError,
    LLMError
)

logger = logging.getLogger(__name__)

class RAGAnswerService:
    """Orchestrates RAG retrieval, context formatting, prompt construction, and LLM text generation."""

    def __init__(self):
        self.retrieval_service = RetrievalService()
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.llm_service = LLMService()

    def answer_question(self, query: str, teacher_id: Any, top_k: int = 3) -> Dict[str, Any]:
        """
        Executes end-to-end RAG question answering pipeline for a given teacher.
        
        Args:
            query: User's question string.
            teacher_id: Authenticated teacher ID.
            top_k: Number of relevant chunks to retrieve.

        Returns:
            Dict containing answer, retrieved_chunks, sources, status, and metadata.
        """
        clean_query = query.strip() if query else ""
        if not clean_query:
            return {
                'query': '',
                'answer': 'Please enter a valid question.',
                'status': 'INVALID_QUERY',
                'has_context': False,
                'retrieved_chunks': [],
                'sources': [],
                'error_detail': 'Empty query.'
            }

        # 1. Retrieve top-k context chunks for the authenticated teacher
        try:
            chunks = self.retrieval_service.retrieve_relevant_context(
                query=clean_query,
                teacher_id=teacher_id,
                top_k=top_k
            )
        except Exception as e:
            logger.error(f"RAG retrieval failed for teacher {teacher_id}: {str(e)}", exc_info=True)
            return {
                'query': clean_query,
                'answer': 'An error occurred while retrieving relevant course documents.',
                'status': 'RETRIEVAL_ERROR',
                'has_context': False,
                'retrieved_chunks': [],
                'sources': [],
                'error_detail': str(e)
            }

        # Extract unique sources list
        sources = []
        seen_sources = set()
        for chunk in chunks:
            fname = chunk.get('source_filename', 'Unknown')
            pg = chunk.get('page_number')
            sld = chunk.get('slide_number')
            key = (fname, pg, sld)
            if key not in seen_sources:
                seen_sources.add(key)
                sources.append({
                    'filename': fname,
                    'page_number': pg,
                    'slide_number': sld
                })

        # 2. Check no-context condition
        if not chunks:
            return {
                'query': clean_query,
                'answer': 'I could not find relevant information in your uploaded material to answer this question.',
                'status': 'NO_CONTEXT',
                'has_context': False,
                'retrieved_chunks': [],
                'sources': [],
                'error_detail': None
            }

        # 3. Format context & build prompt
        formatted_context = self.context_builder.build_context(chunks)
        user_prompt, system_prompt = self.prompt_builder.build_rag_prompt(clean_query, formatted_context)

        # 4. Invoke LLMService
        try:
            raw_answer = self.llm_service.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt
            )
            return {
                'query': clean_query,
                'answer': raw_answer.strip(),
                'status': 'SUCCESS',
                'has_context': True,
                'retrieved_chunks': chunks,
                'sources': sources,
                'error_detail': None
            }
        except LLMConnectionError as e:
            logger.warning(f"Ollama connection error during RAG generation: {str(e)}")
            return {
                'query': clean_query,
                'answer': 'Local Ollama AI service is currently offline. Please ensure Ollama is running.',
                'status': 'LLM_UNAVAILABLE',
                'has_context': True,
                'retrieved_chunks': chunks,
                'sources': sources,
                'error_detail': str(e)
            }
        except LLMTimeoutError as e:
            logger.warning(f"Ollama timeout error during RAG generation: {str(e)}")
            return {
                'query': clean_query,
                'answer': 'The AI generation request timed out after waiting for Ollama response.',
                'status': 'LLM_TIMEOUT',
                'has_context': True,
                'retrieved_chunks': chunks,
                'sources': sources,
                'error_detail': str(e)
            }
        except LLMInvalidModelError as e:
            logger.error(f"Invalid model tag error during RAG generation: {str(e)}")
            return {
                'query': clean_query,
                'answer': 'Configured LLM model is missing or invalid in Ollama.',
                'status': 'LLM_ERROR',
                'has_context': True,
                'retrieved_chunks': chunks,
                'sources': sources,
                'error_detail': str(e)
            }
        except (LLMResponseError, LLMError, Exception) as e:
            logger.error(f"Unexpected LLM generation error: {str(e)}", exc_info=True)
            return {
                'query': clean_query,
                'answer': 'An unexpected error occurred while generating the AI answer.',
                'status': 'ERROR',
                'has_context': True,
                'retrieved_chunks': chunks,
                'sources': sources,
                'error_detail': str(e)
            }
