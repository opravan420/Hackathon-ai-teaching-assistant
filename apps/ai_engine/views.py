from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404
from django.conf import settings
from apps.ai_engine.services.llm_service import LLMService
from apps.ai_engine.exceptions import LLMError
import logging

logger = logging.getLogger(__name__)

@login_required
def ai_test_view(request):
    # Safeguard 1: Development only (guarantees endpoint cannot be exposed in production)
    if not settings.DEBUG:
        raise Http404("Development endpoint only.")
        
    # Safeguard 2: Product authorization - strictly requires Teacher role
    if request.user.role != 'TEACHER':
        return HttpResponseForbidden("Access restricted to teachers only.")

    llm_service = LLMService()
    
    # Lightweight infrastructure health check (does NOT run active inference)
    health = llm_service.perform_health_check()
    
    prompt = request.POST.get('prompt', '').strip()
    response_text = ""
    error_message = ""
    
    if request.method == 'POST':
        if not prompt:
            error_message = "Prompt cannot be empty."
        else:
            try:
                response_text = llm_service.generate_text(prompt)
            except LLMError as e:
                error_message = str(e)
                logger.error(f"LLM Error during test prompt generation: {error_message}")
            except Exception as e:
                error_message = "An unexpected error occurred during inference."
                logger.error(f"Unexpected error in AI test prompt execution: {str(e)}", exc_info=True)
                
    return render(request, 'ai_engine/test.html', {
        'health': health,
        'prompt': prompt,
        'response_text': response_text,
        'error_message': error_message
    })
