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

@login_required
def ai_document_test_view(request):
    # Safeguard 1: Development only
    if not settings.DEBUG:
        raise Http404("Development endpoint only.")
        
    # Safeguard 2: Product authorization - strictly requires Teacher role
    if request.user.role != 'TEACHER':
        return HttpResponseForbidden("Access restricted to teachers only.")

    document = None
    error_message = ""
    success_message = ""

    if request.method == 'POST':
        uploaded_file = request.FILES.get('document_file')
        if not uploaded_file:
            error_message = "Please select a file to upload."
        else:
            from apps.ai_engine.document_processing.service import DocumentService
            from apps.ai_engine.document_processing.exceptions import DocumentError
            
            service = DocumentService()
            try:
                document = service.process_document(request.user, uploaded_file)
                success_message = f"File '{document.original_filename}' processed successfully!"
            except DocumentError as e:
                error_message = str(e)
            except Exception as e:
                error_message = "An unexpected error occurred during document processing."
                logger.error(f"Error in document processing view: {str(e)}", exc_info=True)

    # Fetch previous historical documents for this teacher
    from apps.ai_engine.models import Document
    documents = Document.objects.filter(teacher=request.user).order_by('-created_at')

    return render(request, 'ai_engine/document_test.html', {
        'document': document,
        'documents': documents,
        'error_message': error_message,
        'success_message': success_message
    })

