import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404, JsonResponse
from django.conf import settings
from apps.ai_engine.services.llm_service import LLMService
from apps.ai_engine.exceptions import LLMError
from apps.ai_engine.task_tracker import TaskTracker

logger = logging.getLogger(__name__)

@login_required
def task_status_api(request, task_id):
    """
    Central API endpoint for frontend task status & progress polling.
    Returns task state, progress percentage, current stage label, and dynamic message.
    Includes persistent database lookup for StudentSubmission records.
    """
    tracker = TaskTracker()
    task = tracker.get_task(task_id)
    if not task:
        from apps.grading.models import StudentSubmission
        sub = StudentSubmission.objects.filter(task_id=task_id).select_related('result').first()
        if sub:
            if sub.status == 'COMPLETED' and hasattr(sub, 'result') and sub.result:
                from django.urls import reverse
                redirect_url = reverse('grading_result_review', kwargs={'result_id': sub.result.id})
                return JsonResponse({
                    'task_id': task_id,
                    'status': 'COMPLETED',
                    'progress': 100,
                    'stage': 'COMPLETED',
                    'stage_label': 'Grading Completed',
                    'message': 'Evaluation completed successfully!',
                    'redirect_url': redirect_url
                })
            elif sub.status == 'FAILED':
                return JsonResponse({
                    'task_id': task_id,
                    'status': 'FAILED',
                    'progress': 0,
                    'stage': 'FAILED',
                    'stage_label': 'Evaluation Failed',
                    'message': sub.error_message or 'Evaluation failed.',
                    'error': sub.error_message or 'Evaluation failed.'
                })

        return JsonResponse({
            'task_id': task_id,
            'status': 'FAILED',
            'progress': 0,
            'stage': 'FAILED',
            'stage_label': 'Task Not Found',
            'message': 'The specified task ID could not be found.',
            'error': 'Task not found.'
        }, status=200)

    return JsonResponse(task)

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

@login_required
def ai_rag_test_view(request):
    # Safeguard 1: Development only
    if not settings.DEBUG:
        raise Http404("Development endpoint only.")

    # Safeguard 2: Strictly requires Teacher role
    if request.user.role != 'TEACHER':
        return HttpResponseForbidden("Access restricted to teachers only.")

    from apps.ai_engine.rag.retrieval_service import RetrievalService
    from apps.ai_engine.models import Document

    retrieval_service = RetrievalService()
    query = ""
    top_k = 3
    results = []
    error_message = ""
    success_message = ""

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'rebuild':
            try:
                res = retrieval_service.rebuild_index_for_teacher(request.user.id)
                if res['status'] == 'EMPTY':
                    success_message = "Teacher index cleared (no valid documents found)."
                else:
                    success_message = f"Successfully rebuilt index! {res['chunk_count']} chunks indexed across {res['document_count']} documents."
            except Exception as e:
                error_message = f"Failed to rebuild index: {str(e)}"
                logger.error(f"Error rebuilding index for teacher {request.user.id}: {str(e)}", exc_info=True)

        elif action == 'search' or 'query' in request.POST:
            query = request.POST.get('query', '').strip()
            try:
                top_k_str = request.POST.get('top_k', '3')
                top_k = int(top_k_str) if top_k_str.isdigit() else 3
            except ValueError:
                top_k = 3

            if not query:
                error_message = "Please enter a search query."
            else:
                try:
                    results = retrieval_service.retrieve_relevant_context(
                        query=query,
                        teacher_id=request.user.id,
                        top_k=top_k
                    )
                    if not results:
                        success_message = "Query executed successfully, but no matching context was found in your indexed documents."
                except Exception as e:
                    error_message = f"Retrieval failed: {str(e)}"
                    logger.error(f"Error executing RAG query for teacher {request.user.id}: {str(e)}", exc_info=True)

    documents = Document.objects.filter(teacher=request.user).order_by('-created_at')

    return render(request, 'ai_engine/rag_test.html', {
        'query': query,
        'top_k': top_k,
        'results': results,
        'documents': documents,
        'error_message': error_message,
        'success_message': success_message
    })

@login_required
def ai_rag_gemma_test_view(request):
    # Safeguard 1: Development only
    if not settings.DEBUG:
        raise Http404("Development endpoint only.")

    # Safeguard 2: Strictly requires Teacher role
    if request.user.role != 'TEACHER':
        return HttpResponseForbidden("Access restricted to teachers only.")

    from apps.ai_engine.rag.rag_answer_service import RAGAnswerService

    rag_answer_service = RAGAnswerService()
    llm_health = LLMService().perform_health_check()

    query = ""
    top_k = 3
    rag_result = None
    error_message = ""
    success_message = ""

    if request.method == 'POST':
        query = request.POST.get('query', '').strip()
        top_k_str = request.POST.get('top_k', '3')
        top_k = int(top_k_str) if top_k_str.isdigit() else 3

        if not query:
            error_message = "Please enter a question to ask Gemma."
        else:
            try:
                rag_result = rag_answer_service.answer_question(
                    query=query,
                    teacher_id=request.user.id,
                    top_k=top_k
                )
                if rag_result.get('status') == 'NO_CONTEXT':
                    success_message = "Query processed. No relevant context was found in your indexed documents."
                elif rag_result.get('status') == 'SUCCESS':
                    success_message = "Grounded response successfully generated by Gemma 3 4B!"
                else:
                    error_message = rag_result.get('answer')
            except Exception as e:
                error_message = f"RAG + Gemma generation failed: {str(e)}"
                logger.error(f"Error in ai_rag_gemma_test_view: {str(e)}", exc_info=True)

    return render(request, 'ai_engine/rag_gemma_test.html', {
        'query': query,
        'top_k': top_k,
        'rag_result': rag_result,
        'llm_health': llm_health,
        'error_message': error_message,
        'success_message': success_message
    })
