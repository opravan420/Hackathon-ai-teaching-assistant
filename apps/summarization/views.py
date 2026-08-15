from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from .models import LectureSummary

@login_required
def summary_dashboard(request):
    summaries = LectureSummary.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'summarization/dashboard.html', {'summaries': summaries})

@login_required
def summary_create(request):
    if request.method == 'POST':
        source_file = request.FILES.get('source_file')
        if not source_file:
            messages.error(request, "Please upload a valid file.")
            return redirect('summary_create')
            
        # Simulation summary text
        mock_summary = f"""# EXECUTIVE SUMMARY FOR {source_file.name}

## 1. Core Concepts
This lecture note explores the fundamentals of the course material. Key highlights include basic definitions, architectural structures, and design considerations.

## 2. Key Takeaways
- **Efficiency**: Implementing clean code design patterns reduces memory footprint by up to 40%.
- **Robustness**: Database-level constraints prevent data duplications and reference leaks.
- **Modularity**: Dividing projects into standalone app modules simplifies verification and deployment.

## 3. Conclusion
The document outlines a structured methodology to build and scale applications efficiently.
"""
        summary = LectureSummary.objects.create(
            teacher=request.user,
            source_file_name=source_file.name,
            summary_text=mock_summary
        )
        messages.success(request, "AI Note Summary generated successfully (Simulation)!")
        return redirect('summary_review', summary_id=summary.id)
        
    return render(request, 'summarization/create.html')

@login_required
def summary_review(request, summary_id):
    summary = get_object_or_404(LectureSummary, id=summary_id, teacher=request.user)
    if request.method == 'POST':
        summary_text = request.POST.get('summary_text')
        is_satisfactory = request.POST.get('is_satisfactory') == 'true'
        if summary_text:
            summary.summary_text = summary_text
            summary.is_satisfactory = is_satisfactory
            summary.save()
            messages.success(request, "Summary updated successfully.")
            return redirect('summary_review', summary_id=summary.id)
            
    return render(request, 'summarization/review.html', {'summary': summary})

@login_required
def summary_download_pdf(request, summary_id):
    summary = get_object_or_404(LectureSummary, id=summary_id, teacher=request.user)
    # Simple plain text file disguised as PDF for hackathon Phase 1
    response = HttpResponse(summary.summary_text, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Summary_{summary_id}.pdf"'
    return response

@login_required
def summary_download_docx(request, summary_id):
    summary = get_object_or_404(LectureSummary, id=summary_id, teacher=request.user)
    response = HttpResponse(summary.summary_text, content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="Summary_{summary_id}.docx"'
    return response
