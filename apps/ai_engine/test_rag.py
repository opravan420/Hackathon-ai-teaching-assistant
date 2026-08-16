import os
import shutil
import numpy as np
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.signals import template_rendered
from apps.accounts.models import TeacherProfile
from apps.ai_engine.models import Document
from apps.ai_engine.rag.chunking_service import ChunkingService
from apps.ai_engine.rag.embedding_service import EmbeddingService
from apps.ai_engine.rag.vector_store import VectorStoreManager
from apps.ai_engine.rag.retrieval_service import RetrievalService
from apps.ai_engine.document_processing.service import DocumentService

# Workaround for Django 5.0 template context copying on Python 3.14
template_rendered.disconnect()

User = get_user_model()

class RAGCoreUnitTestCase(TestCase):
    def setUp(self):
        self.teacher_1 = User.objects.create_user(
            username='rag_teacher1', password='password123', role=User.TEACHER
        )
        self.profile_1 = TeacherProfile.objects.create(
            user=self.teacher_1, employee_id='EMP_RAG1', department='Physics'
        )

        self.teacher_2 = User.objects.create_user(
            username='rag_teacher2', password='password123', role=User.TEACHER
        )
        self.profile_2 = TeacherProfile.objects.create(
            user=self.teacher_2, employee_id='EMP_RAG2', department='Chemistry'
        )

        self.doc_service = DocumentService()

    def tearDown(self):
        for t_id in [self.teacher_1.id, self.teacher_2.id]:
            vsm = VectorStoreManager()
            vsm._delete_teacher_files(t_id)

    # 1. Chunking Service Tests
    def test_chunking_basic_size_and_overlap(self):
        chunker = ChunkingService(chunk_size=100, chunk_overlap=20)
        text = "Paragraph 1 sentence.\n\nParagraph 2 sentence which is a bit longer to test unit splitting."
        chunks = chunker.chunk_text(text, document_id=1, teacher_id=self.teacher_1.id, source_filename="test.txt")
        self.assertTrue(len(chunks) >= 1)
        for c in chunks:
            self.assertLessEqual(len(c['chunk_text']), 100)
            self.assertEqual(c['document_id'], 1)
            self.assertEqual(c['teacher_id'], str(self.teacher_1.id))

    def test_chunking_hindi_english_unicode(self):
        chunker = ChunkingService(chunk_size=200, chunk_overlap=50)
        text = "[Page 1]\nDeadlock occurs when four conditions are met.\n[Page 2]\nडेडलॉक तब होता है जब चार शर्तें पूरी होती हैं।"
        chunks = chunker.chunk_text(text, document_id=2, teacher_id=self.teacher_1.id, source_filename="operating_systems.pdf")
        self.assertEqual(len(chunks), 2)
        
        self.assertEqual(chunks[0]['page_number'], 1)
        self.assertIn("Deadlock occurs", chunks[0]['chunk_text'])

        self.assertEqual(chunks[1]['page_number'], 2)
        self.assertIn("डेडलॉक तब होता है", chunks[1]['chunk_text'])

    def test_chunking_pptx_slide_metadata(self):
        chunker = ChunkingService(chunk_size=200, chunk_overlap=50)
        text = "[Slide 1]\nIntroduction to CPU Scheduling\n\n[Slide 2]\nFirst-Come First-Served Algorithm"
        chunks = chunker.chunk_text(text, document_id=3, teacher_id=self.teacher_1.id, source_filename="lecture.pptx")
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]['slide_number'], 1)
        self.assertEqual(chunks[1]['slide_number'], 2)

    def test_empty_query_and_empty_document(self):
        retrieval = RetrievalService()
        res = retrieval.retrieve_relevant_context("", teacher_id=self.teacher_1.id)
        self.assertEqual(res, [])

        chunker = ChunkingService()
        chunks = chunker.chunk_text("", document_id=4, teacher_id=self.teacher_1.id, source_filename="empty.txt")
        self.assertEqual(chunks, [])

    # 2. Teacher Isolation and Search Tests using Embeddings
    def test_teacher_isolation(self):
        doc1 = Document.objects.create(
            teacher=self.teacher_1,
            original_filename="t1_secret.txt",
            stored_file="documents/t1_secret.txt",
            file_type="TXT",
            file_size=100,
            extraction_status=Document.SUCCESS,
            extracted_text="Teacher 1 confidential quantum computing lecture note.",
            character_count=50
        )

        doc2 = Document.objects.create(
            teacher=self.teacher_2,
            original_filename="t2_chemistry.txt",
            stored_file="documents/t2_chemistry.txt",
            file_type="TXT",
            file_size=100,
            extraction_status=Document.SUCCESS,
            extracted_text="Teacher 2 organic chemistry reaction mechanism.",
            character_count=50
        )

        vsm = VectorStoreManager()
        res1 = vsm.build_teacher_index(self.teacher_1.id)
        res2 = vsm.build_teacher_index(self.teacher_2.id)

        self.assertEqual(res1['status'], 'SUCCESS')
        self.assertEqual(res2['status'], 'SUCCESS')

        doc1.refresh_from_db()
        doc2.refresh_from_db()
        self.assertEqual(doc1.indexing_status, Document.INDEXED)
        self.assertEqual(doc2.indexing_status, Document.INDEXED)

        retrieval = RetrievalService()
        t1_results = retrieval.retrieve_relevant_context("quantum computing", teacher_id=self.teacher_1.id, top_k=5)
        self.assertTrue(len(t1_results) > 0)
        for item in t1_results:
            self.assertEqual(item['teacher_id'], str(self.teacher_1.id))
            self.assertIn("quantum computing", item['chunk_text'].lower())

        t2_results = retrieval.retrieve_relevant_context("quantum computing", teacher_id=self.teacher_2.id, top_k=5)
        for item in t2_results:
            self.assertEqual(item['teacher_id'], str(self.teacher_2.id))
            self.assertNotIn("quantum computing", item['chunk_text'].lower())

    # 3. Document Deletion & Re-indexing Test
    def test_document_deletion_reindexing(self):
        doc1 = Document.objects.create(
            teacher=self.teacher_1,
            original_filename="deadlock.txt",
            stored_file="documents/deadlock.txt",
            file_type="TXT",
            file_size=100,
            extraction_status=Document.SUCCESS,
            extracted_text="Deadlock occurs when four conditions hold simultaneously.",
            character_count=50
        )

        retrieval = RetrievalService()
        retrieval.rebuild_index_for_teacher(self.teacher_1.id)

        results_before = retrieval.retrieve_relevant_context("deadlock", teacher_id=self.teacher_1.id)
        self.assertTrue(len(results_before) > 0)

        self.doc_service.delete_document(doc1)

        results_after = retrieval.retrieve_relevant_context("deadlock", teacher_id=self.teacher_1.id)
        self.assertEqual(results_after, [])


class RAGEndpointSafeguardsTestCase(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='rag_teacher_view', password='password123', role=User.TEACHER
        )
        self.admin = User.objects.create_user(
            username='rag_admin_view', password='password123', role=User.ADMIN
        )

    @override_settings(DEBUG=True)
    def test_rag_view_requires_teacher_role(self):
        client = Client()
        client.login(username='rag_admin_view', password='password123')
        response = client.get(reverse('ai_rag_test_view'))
        self.assertEqual(response.status_code, 403)

    @override_settings(DEBUG=False)
    def test_rag_view_returns_404_when_debug_false(self):
        client = Client()
        client.login(username='rag_teacher_view', password='password123')
        response = client.get(reverse('ai_rag_test_view'))
        self.assertEqual(response.status_code, 404)


class BGEM3LiveIntegrationTestCase(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='bge_live_teacher', password='password123', role=User.TEACHER
        )

    def tearDown(self):
        VectorStoreManager()._delete_teacher_files(self.teacher.id)

    def test_live_bge_m3_retrieval(self):
        embedding_service = EmbeddingService()

        english_texts = [
            "Operating systems manage hardware resources and process scheduling.",
            "Four necessary conditions for deadlock are mutual exclusion, hold and wait, no preemption, and circular wait.",
            "Virtual memory combines RAM and disk space for large programs."
        ]
        hindi_texts = [
            "डेडलॉक एक ऐसी स्थिति है जहां दो या अधिक प्रोसेस एक दूसरे के रिसोर्स का इंतजार करते हैं।",
            "ऑपरेटिंग सिस्टम कंप्यूटर के हार्डवेयर और सॉफ्टवेयर रिसोर्स को मैनेज करता है।"
        ]

        try:
            eng_vecs = embedding_service.generate_embeddings(english_texts)
            hin_vecs = embedding_service.generate_embeddings(hindi_texts)

            dim = embedding_service.get_embedding_dimension()
            self.assertEqual(eng_vecs.shape, (3, dim))
            self.assertEqual(hin_vecs.shape, (2, dim))

            doc = Document.objects.create(
                teacher=self.teacher,
                original_filename="operating_systems_notes.txt",
                stored_file="documents/os_notes.txt",
                file_type="TXT",
                file_size=200,
                extraction_status=Document.SUCCESS,
                extracted_text="\n\n".join(english_texts + hindi_texts),
                character_count=500
            )

            retrieval = RetrievalService()
            build_res = retrieval.rebuild_index_for_teacher(self.teacher.id)
            self.assertEqual(build_res['status'], 'SUCCESS')

            # English semantic retrieval check
            eng_query = "What are the four necessary conditions for deadlock?"
            eng_results = retrieval.retrieve_relevant_context(eng_query, teacher_id=self.teacher.id, top_k=3)
            self.assertTrue(len(eng_results) > 0)
            top_eng_text = eng_results[0]['chunk_text']
            self.assertIn("Four necessary conditions for deadlock", top_eng_text)

            # Hindi semantic retrieval check
            hin_query = "डेडलॉक क्या है?"
            hin_results = retrieval.retrieve_relevant_context(hin_query, teacher_id=self.teacher.id, top_k=3)
            self.assertTrue(len(hin_results) > 0)
            top_hin_text = hin_results[0]['chunk_text']
            self.assertIn("डेडलॉक एक ऐसी स्थिति है", top_hin_text)

            print("\n[LIVE BGE-M3 INTEGRATION TEST PASSED] English & Hindi Retrieval Verified!")

        except Exception as e:
            self.fail(f"Live BGE-M3 integration test failed: {str(e)}")
