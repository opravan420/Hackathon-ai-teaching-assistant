from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import TeacherProfile
from apps.ai_engine.exceptions import (
    LLMConnectionError,
    LLMTimeoutError,
    LLMInvalidModelError,
    LLMResponseError
)
from apps.ai_engine.services.llm_service import LLMService
from unittest.mock import patch, MagicMock
import urllib.request
import urllib.error
import socket
import json

User = get_user_model()

class AIEngineUnitTestCase(TestCase):
    def setUp(self):
        # Setup teacher user
        self.teacher_user = User.objects.create_user(
            username='teacher_ai', password='password123', role=User.TEACHER
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher_user, employee_id='EMP_AI', department='Math'
        )
        self.client = Client()
        self.client.login(username='teacher_ai', password='password123')
        self.service = LLMService()

    @patch('urllib.request.urlopen')
    def test_generation_success(self, mock_urlopen):
        # Mock Response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "model": "gemma3:4b",
            "response": "This is a mocked gemma text response.",
            "done": True
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        text = self.service.generate_text("Hello Gemma")
        self.assertEqual(text, "This is a mocked gemma text response.")
        
    @patch('urllib.request.urlopen')
    def test_connection_error(self, mock_urlopen):
        # Mock URLError (connection refused)
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        with self.assertRaises(LLMConnectionError):
            self.service.generate_text("Hello Gemma")

    @patch('urllib.request.urlopen')
    def test_timeout_error(self, mock_urlopen):
        # Mock socket.timeout
        mock_urlopen.side_effect = socket.timeout("timed out")
        
        with self.assertRaises(LLMTimeoutError):
            self.service.generate_text("Hello Gemma")

    @patch('urllib.request.urlopen')
    def test_invalid_model_error(self, mock_urlopen):
        # Mock HTTPError 404 (model missing)
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="http://localhost:11434/api/generate",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None
        )
        
        with self.assertRaises(LLMInvalidModelError):
            self.service.generate_text("Hello Gemma")

    @patch('urllib.request.urlopen')
    def test_empty_response(self, mock_urlopen):
        # Mock JSON response missing the response key
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "done": True
        }).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        with self.assertRaises(LLMResponseError):
            self.service.generate_text("Hello Gemma")


class AIEngineIntegrationTestCase(TestCase):
    def setUp(self):
        self.service = LLMService()

    def test_live_ollama_gemma_connection(self):
        # Check if Ollama is online first
        health = self.service.perform_health_check()
        if health["ollama_status"] != "AVAILABLE" or health["model_status"] != "READY":
            # Skip live integration test if the model is not found or Ollama is offline
            self.skipTest(f"Ollama local service is not online or model is not READY. Reason: {health['reason']}")
            
        # Run a real test query
        try:
            response = self.service.generate_text("Explain deadlock in operating systems in 1 sentence.")
            self.assertTrue(len(response) > 0)
            print(f"\n[LIVE INTEGRATION TEST PASSED] Gemma response: {response}")
        except Exception as e:
            self.fail(f"Live Gemma inference failed: {str(e)}")
