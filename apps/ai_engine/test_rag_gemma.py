import os
import unittest
import socket
import urllib.request
from unittest.mock import MagicMock, patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.test.signals import template_rendered

from apps.accounts.models import TeacherProfile
from apps.ai_engine.models import Document
from apps.ai_engine.prompting.context_builder import ContextBuilder
from apps.ai_engine.prompting.prompt_builder import PromptBuilder
from apps.ai_engine.rag.rag_answer_service import RAGAnswerService
from apps.ai_engine.exceptions import (
    LLMConnectionError,
    LLMTimeoutError,
    LLMInvalidModelError,
    LLMResponseError
)

template_rendered.disconnect()
User = get_user_model()


class ContextBuilderTestCase(TestCase):
    def setUp(self):
        self.builder = ContextBuilder()

    def test_build_context_basic_formatting(self):
        chunks = [
            {
                'chunk_text': 'Mutual exclusion requires exclusive access to resources.',
                'source_filename': 'operating_systems.pdf',
                'page_number': 10,
                'slide_number': None,
                'similarity_score': 0.895
            },
            {
                'chunk_text': 'Slide 2 details hold and wait condition.',
                'source_filename': 'deadlock_lecture.pptx',
                'page_number': None,
                'slide_number': 2,
                'similarity_score': 0.742
            }
        ]
        context_str = self.builder.build_context(chunks)
        self.assertIn("SOURCE: operating_systems.pdf | PAGE: 10", context_str)
        self.assertIn("SOURCE: deadlock_lecture.pptx | SLIDE: 2", context_str)
        self.assertIn("Mutual exclusion requires exclusive access to resources.", context_str)
        # Verify similarity scores are NOT in the model context string
        self.assertNotIn("0.895", context_str)
        self.assertNotIn("0.742", context_str)
        self.assertNotIn("Similarity Score", context_str)

    def test_build_context_empty_list(self):
        self.assertEqual(self.builder.build_context([]), "")


class PromptBuilderTestCase(TestCase):
    def setUp(self):
        self.builder = PromptBuilder()

    def test_build_rag_prompt_structure(self):
        context = "SOURCE: doc.txt\nDeadlock happens when processes wait for each other."
        query = "What is deadlock?"
        user_prompt, system_prompt = self.builder.build_rag_prompt(query, context)

        self.assertIn("DOCUMENT CONTEXT:", user_prompt)
        self.assertIn(context, user_prompt)
        self.assertIn("USER QUESTION:\nWhat is deadlock?", user_prompt)
        self.assertIn("base your answer strictly on the provided material", system_prompt.lower())


class RAGAnswerServiceUnitTest(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='rag_service_teacher', password='password123', role=User.TEACHER
        )
        self.service = RAGAnswerService()

    def test_empty_query_validation(self):
        res = self.service.answer_question("", teacher_id=self.teacher.id)
        self.assertEqual(res['status'], 'INVALID_QUERY')
        self.assertEqual(res['answer'], 'Please enter a valid question.')

    @patch('apps.ai_engine.rag.rag_answer_service.RetrievalService')
    def test_no_context_behavior(self, MockRetrieval):
        mock_retrieval_inst = MagicMock()
        mock_retrieval_inst.retrieve_relevant_context.return_value = []
        MockRetrieval.return_value = mock_retrieval_inst

        service = RAGAnswerService()
        res = service.answer_question("Unrelated topic", teacher_id=self.teacher.id)
        self.assertEqual(res['status'], 'NO_CONTEXT')
        self.assertFalse(res['has_context'])
        self.assertIn("could not find relevant information", res['answer'])

    @patch('apps.ai_engine.rag.rag_answer_service.LLMService')
    @patch('apps.ai_engine.rag.rag_answer_service.RetrievalService')
    def test_successful_rag_answer_flow(self, MockRetrieval, MockLLM):
        mock_retrieval_inst = MagicMock()
        mock_retrieval_inst.retrieve_relevant_context.return_value = [
            {
                'chunk_text': 'Deadlock requires 4 conditions.',
                'source_filename': 'os.pdf',
                'page_number': 5,
                'slide_number': None,
                'similarity_score': 0.91
            }
        ]
        MockRetrieval.return_value = mock_retrieval_inst

        mock_llm_inst = MagicMock()
        mock_llm_inst.generate_text.return_value = "The four conditions for deadlock are mutual exclusion, hold & wait, no preemption, and circular wait."
        MockLLM.return_value = mock_llm_inst

        service = RAGAnswerService()
        res = service.answer_question("What are deadlock conditions?", teacher_id=self.teacher.id)

        self.assertEqual(res['status'], 'SUCCESS')
        self.assertTrue(res['has_context'])
        self.assertIn("mutual exclusion", res['answer'])
        self.assertEqual(len(res['sources']), 1)
        self.assertEqual(res['sources'][0]['filename'], 'os.pdf')

    @patch('apps.ai_engine.rag.rag_answer_service.LLMService')
    @patch('apps.ai_engine.rag.rag_answer_service.RetrievalService')
    def test_ollama_offline_error_handling(self, MockRetrieval, MockLLM):
        mock_retrieval_inst = MagicMock()
        mock_retrieval_inst.retrieve_relevant_context.return_value = [{'chunk_text': 'some context', 'source_filename': 'f.txt'}]
        MockRetrieval.return_value = mock_retrieval_inst

        mock_llm_inst = MagicMock()
        mock_llm_inst.generate_text.side_effect = LLMConnectionError("Connection refused")
        MockLLM.return_value = mock_llm_inst

        service = RAGAnswerService()
        res = service.answer_question("query", teacher_id=self.teacher.id)

        self.assertEqual(res['status'], 'LLM_UNAVAILABLE')
        self.assertIn("offline", res['answer'])

    @patch('apps.ai_engine.rag.rag_answer_service.LLMService')
    @patch('apps.ai_engine.rag.rag_answer_service.RetrievalService')
    def test_ollama_timeout_error_handling(self, MockRetrieval, MockLLM):
        mock_retrieval_inst = MagicMock()
        mock_retrieval_inst.retrieve_relevant_context.return_value = [{'chunk_text': 'some context', 'source_filename': 'f.txt'}]
        MockRetrieval.return_value = mock_retrieval_inst

        mock_llm_inst = MagicMock()
        mock_llm_inst.generate_text.side_effect = LLMTimeoutError("Timed out after 120s")
        MockLLM.return_value = mock_llm_inst

        service = RAGAnswerService()
        res = service.answer_question("query", teacher_id=self.teacher.id)

        self.assertEqual(res['status'], 'LLM_TIMEOUT')
        self.assertIn("timed out", res['answer'].lower())


class RAGGemmaEndpointSafeguardsTestCase(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='rag_gemma_teacher_view', password='password123', role=User.TEACHER
        )
        self.admin = User.objects.create_user(
            username='rag_gemma_admin_view', password='password123', role=User.ADMIN
        )

    @override_settings(DEBUG=True)
    def test_rag_gemma_view_requires_teacher_role(self):
        client = Client()
        client.login(username='rag_gemma_admin_view', password='password123')
        response = client.get(reverse('ai_rag_gemma_test_view'))
        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=False)
    def test_rag_gemma_view_returns_404_when_debug_false(self):
        client = Client()
        client.login(username='rag_gemma_teacher_view', password='password123')
        response = client.get(reverse('ai_rag_gemma_test_view'))
        self.assertEqual(response.status_code, 404)


def _is_ollama_and_gemma_available():
    api_base = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434').rstrip('/')
    model_tag = os.getenv('OLLAMA_MODEL_TAG', 'gemma3:4b')
    try:
        req = urllib.request.Request(f"{api_base}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = resp.read().decode('utf-8')
            return model_tag in data
    except Exception:
        return False


class BGEM3Gemma3LiveIntegrationTestCase(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='bge_gemma_live_teacher', password='password123', role=User.TEACHER
        )

    def tearDown(self):
        from apps.ai_engine.rag.vector_store import VectorStoreManager
        VectorStoreManager()._delete_teacher_files(self.teacher.id)

    @unittest.skipUnless(_is_ollama_and_gemma_available(), "Ollama or Gemma 3 4B is not running locally.")
    def test_live_rag_plus_gemma_flow(self):
        # Create document with known content
        doc = Document.objects.create(
            teacher=self.teacher,
            original_filename="operating_systems_notes.txt",
            stored_file="documents/os_notes.txt",
            file_type="TXT",
            file_size=300,
            extraction_status=Document.SUCCESS,
            extracted_text=(
                "Deadlock is a state in an operating system where a set of processes are blocked.\n\n"
                "The four necessary conditions for deadlock are:\n"
                "1. Mutual Exclusion\n"
                "2. Hold and Wait\n"
                "3. No Preemption\n"
                "4. Circular Wait.\n\n"
                "डेडलॉक एक ऐसी स्थिति है जहां दो या अधिक प्रोसेस एक दूसरे के रिसोर्स का इंतजार करते हैं।"
            ),
            character_count=400
        )

        from apps.ai_engine.rag.retrieval_service import RetrievalService
        retrieval_service = RetrievalService()
        retrieval_service.rebuild_index_for_teacher(self.teacher.id)

        rag_answer_service = RAGAnswerService()

        # 1. English live question
        res_eng = rag_answer_service.answer_question(
            query="What are the four necessary conditions for deadlock?",
            teacher_id=self.teacher.id,
            top_k=3
        )
        self.assertEqual(res_eng['status'], 'SUCCESS')
        self.assertTrue(res_eng['has_context'])
        self.assertIn("Mutual Exclusion", res_eng['answer'])

        # 2. Hindi live question
        res_hin = rag_answer_service.answer_question(
            query="डेडलॉक क्या है?",
            teacher_id=self.teacher.id,
            top_k=3
        )
        self.assertEqual(res_hin['status'], 'SUCCESS')
        self.assertTrue(res_hin['has_context'])

        print("\n[LIVE RAG + GEMMA 3 4B INTEGRATION TEST PASSED] English & Hindi Grounded Generation Verified!")
