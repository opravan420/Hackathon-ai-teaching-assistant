/**
 * Task Progress & Status UI Engine
 * Provides reusable real-time feedback, milestone stage progression,
 * button disabling against duplicate submissions, and cleanup handlers.
 */

(function () {
    let activeInterval = null;
    let originalSubmitBtnHTML = null;

    const STAGE_PRESETS = {
        'quiz_generation': [
            { pct: 10, label: 'Preparing task...', msg: 'Initializing AI quiz parameters...' },
            { pct: 30, label: 'Reading document...', msg: 'Extracting reference document text & context...' },
            { pct: 50, label: 'Loading AI Model...', msg: 'Connecting to local Gemma 3 4B engine...' },
            { pct: 70, label: 'Generating MCQs...', msg: 'Synthesizing multiple choice questions...' },
            { pct: 88, label: 'Validating MCQs...', msg: 'Verifying option correctness & schema rules...' },
            { pct: 96, label: 'Finalizing...', msg: 'Saving quiz to database...' }
        ],
        'summarization': [
            { pct: 10, label: 'Preparing summarizer...', msg: 'Configuring lecture summarization request...' },
            { pct: 35, label: 'Extracting content...', msg: 'Reading course material and lecture notes...' },
            { pct: 60, label: 'Synthesizing summary...', msg: 'Generating structured lecture summary via AI...' },
            { pct: 90, label: 'Finalizing...', msg: 'Formatting final summary document...' }
        ],
        'grading': [
            { pct: 10, label: 'Preparing grading...', msg: 'Loading master key & grading criteria...' },
            { pct: 35, label: 'Reading answer sheet...', msg: 'Processing student handwriting sheet...' },
            { pct: 65, label: 'Evaluating responses...', msg: 'Grading student answers against reference rubric...' },
            { pct: 92, label: 'Recording scores...', msg: 'Saving feedback and score deductions...' }
        ],
        'document_processing': [
            { pct: 10, label: 'Preparing file...', msg: 'Validating file format and size...' },
            { pct: 40, label: 'Extracting text...', msg: 'Parsing document contents...' },
            { pct: 75, label: 'Building index...', msg: 'Creating vector embeddings & FAISS index...' },
            { pct: 95, label: 'Finalizing...', msg: 'Updating document registry...' }
        ],
        'default': [
            { pct: 15, label: 'Preparing task...', msg: 'Initializing processing environment...' },
            { pct: 45, label: 'Processing...', msg: 'Executing AI model pipeline...' },
            { pct: 80, label: 'Validating...', msg: 'Checking output formatting...' },
            { pct: 95, label: 'Finalizing...', msg: 'Completing task...' }
        ]
    };

    window.initTaskProgress = function (taskType, title) {
        const container = document.getElementById('taskProgressContainer');
        if (!container) return;

        container.classList.remove('hidden');
        
        if (title) {
            const titleEl = document.getElementById('taskProgressTitle');
            if (titleEl) titleEl.innerText = title;
        }

        const errAlert = document.getElementById('taskErrorAlert');
        if (errAlert) errAlert.classList.add('hidden');

        updateBadge('RUNNING', 'bg-indigo-50 text-indigo-600 border-indigo-100');
        
        // Start milestone stage progression
        const stages = STAGE_PRESETS[taskType] || STAGE_PRESETS['default'];
        let stageIdx = 0;

        // Immediately show first stage
        applyStage(stages[0]);

        if (activeInterval) clearInterval(activeInterval);
        
        activeInterval = setInterval(() => {
            stageIdx++;
            if (stageIdx < stages.length) {
                applyStage(stages[stageIdx]);
            }
        }, 1500);
    };

    function applyStage(stageObj) {
        if (!stageObj) return;

        const bar = document.getElementById('taskProgressBar');
        const text = document.getElementById('taskPercentText');
        const label = document.getElementById('taskStageLabel');
        const msg = document.getElementById('taskMessageText');

        if (bar) bar.style.width = stageObj.pct + '%';
        if (text) text.innerText = stageObj.pct + '%';
        if (label) label.innerText = stageObj.label;
        if (msg) msg.innerText = stageObj.msg;
    }

    function updateBadge(text, colorClasses) {
        const badge = document.getElementById('taskStatusBadge');
        if (badge) {
            badge.innerText = text;
            badge.className = `text-xs font-bold font-outfit uppercase px-3 py-1 rounded-full border transition-colors ${colorClasses}`;
        }
    }

    window.updateTaskProgress = function (progressPct, stageLabel, message) {
        applyStage({ pct: progressPct, label: stageLabel, msg: message });
    };

    window.completeTaskProgress = function (message) {
        if (activeInterval) clearInterval(activeInterval);
        applyStage({ pct: 100, label: 'Completed', msg: message || 'Task completed successfully!' });
        updateBadge('COMPLETED', 'bg-emerald-50 text-emerald-700 border-emerald-200');

        const spinner = document.getElementById('taskStatusSpinner');
        if (spinner) {
            spinner.className = 'w-8 h-8 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 shrink-0';
            spinner.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>`;
        }
    };

    window.failTaskProgress = function (errorMessage) {
        if (activeInterval) clearInterval(activeInterval);
        updateBadge('FAILED', 'bg-rose-50 text-rose-700 border-rose-200');

        const errAlert = document.getElementById('taskErrorAlert');
        const errMsgEl = document.getElementById('taskErrorMessage');
        if (errMsgEl) errMsgEl.innerText = errorMessage || 'Task execution failed.';
        if (errAlert) errAlert.classList.remove('hidden');

        const spinner = document.getElementById('taskStatusSpinner');
        if (spinner) {
            spinner.className = 'w-8 h-8 rounded-xl bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600 shrink-0';
            spinner.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>`;
        }
    };

    window.resetTaskProgressUI = function () {
        if (activeInterval) clearInterval(activeInterval);
        const container = document.getElementById('taskProgressContainer');
        if (container) container.classList.add('hidden');

        // Restore submit button
        const form = document.querySelector('form.ai-task-form');
        if (form) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.classList.remove('opacity-60', 'cursor-not-allowed');
                if (originalSubmitBtnHTML) submitBtn.innerHTML = originalSubmitBtnHTML;
            }
        }
    };

    // Auto-bind to forms with class 'ai-task-form'
    document.addEventListener('DOMContentLoaded', function () {
        const forms = document.querySelectorAll('form.ai-task-form');
        forms.forEach(form => {
            form.addEventListener('submit', function (e) {
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    if (!originalSubmitBtnHTML) originalSubmitBtnHTML = submitBtn.innerHTML;
                    submitBtn.disabled = true;
                    submitBtn.classList.add('opacity-60', 'cursor-not-allowed');
                    submitBtn.innerHTML = `
                        <div class="flex items-center justify-center space-x-2">
                            <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            <span>Processing AI Task...</span>
                        </div>
                    `;
                }

                const taskType = form.dataset.taskType || 'default';
                const taskTitle = form.dataset.taskTitle || 'Processing AI Task';
                window.initTaskProgress(taskType, taskTitle);
            });
        });
    });

    // Cleanup interval on page unload / unmount
    window.addEventListener('beforeunload', function () {
        if (activeInterval) clearInterval(activeInterval);
    });

})();
