from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import LectureSummary
from .services import SummarizationService, SummarizationError
from apps.ai_engine.exceptions import LLMError

@login_required
def summary_dashboard(request):
    summaries = LectureSummary.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'summarization/dashboard.html', {'summaries': summaries})

@login_required
def summary_create(request):
    if request.method == 'POST':
        source_file = request.FILES.get('source_file')
        custom_instruction = request.POST.get('custom_instruction', '').strip()
        
        if not source_file:
            messages.error(request, "Please upload a valid document to summarize.")
            return redirect('summary_create')

        sum_service = SummarizationService()
        try:
            summary = sum_service.generate_summary(
                teacher=request.user,
                uploaded_file=source_file,
                custom_instruction=custom_instruction
            )
            messages.success(request, "AI Lecture Note Summary generated successfully!")
            return redirect('summary_review', summary_id=summary.id)

        except (ValueError, SummarizationError, LLMError) as err:
            messages.error(request, f"An error occurred while generating the summary: {str(err)}")
            return redirect('summary_create')
        except Exception as e:
            messages.error(request, f"An error occurred while generating the summary: {str(e)}")
            return redirect('summary_create')
            
    return render(request, 'summarization/create.html')

@login_required
def summary_review(request, summary_id):
    summary = get_object_or_404(LectureSummary, id=summary_id, teacher=request.user)
    if request.method == 'POST':
        summary_text = request.POST.get('summary_text')
        is_satisfactory = request.POST.get('is_satisfactory') == 'true'
        if summary_text:
            summary.summary_text = summary_text.strip()
            summary.is_satisfactory = is_satisfactory
            summary.save()
            messages.success(request, "Summary updated successfully.")
            return redirect('summary_review', summary_id=summary.id)
            
    return render(request, 'summarization/review.html', {'summary': summary})

@login_required
def summary_download_pdf(request, summary_id):
    summary = get_object_or_404(LectureSummary, id=summary_id, teacher=request.user)
    sum_service = SummarizationService()
    pdf_data = sum_service.export_pdf(summary.summary_text, file_name=summary.source_file_name)
    response = HttpResponse(pdf_data, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Summary_{summary_id}.pdf"'
    return response

@login_required
def summary_download_docx(request, summary_id):
    summary = get_object_or_404(LectureSummary, id=summary_id, teacher=request.user)
    sum_service = SummarizationService()
    docx_data = sum_service.export_docx(summary.summary_text, file_name=summary.source_file_name)
    response = HttpResponse(
        docx_data,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    response['Content-Disposition'] = f'attachment; filename="Summary_{summary_id}.docx"'
    return response
