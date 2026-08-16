import time
import uuid
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TaskState:
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    CANCELLED = 'CANCELLED'

class TaskTracker:
    """
    Central thread-safe task status & progress manager for long-running AI operations.
    Tracks task state, progress percentage, current stage, and human-friendly messages.
    """
    _instance = None
    _tasks: Dict[str, Dict[str, Any]] = {}

    # Stage to Percentage & Friendly Label mappings per task type
    STAGE_MAP = {
        'quiz_generation': {
            'PREPARING': (10, 'Preparing quiz configuration...'),
            'READING_DOCUMENT': (25, 'Extracting reference document content...'),
            'LOADING_MODEL': (45, 'Loading local Gemma 3 4B AI model...'),
            'GENERATING': (65, 'Generating questions via AI...'),
            'VALIDATING': (85, 'Validating option correctness & schema...'),
            'FINALIZING': (95, 'Saving quiz to database...'),
            'COMPLETED': (100, 'Quiz generated successfully!')
        },
        'summarization': {
            'PREPARING': (10, 'Preparing summarization parameters...'),
            'READING_DOCUMENT': (30, 'Extracting lecture note content...'),
            'LOADING_MODEL': (50, 'Loading local Gemma 3 4B AI model...'),
            'GENERATING': (75, 'Synthesizing structured lecture summary...'),
            'FINALIZING': (95, 'Finalizing summary document...'),
            'COMPLETED': (100, 'Summary generated successfully!')
        },
        'grading': {
            'PREPARING': (10, 'Preparing grading session...'),
            'READING_DOCUMENT': (25, 'Processing question paper & master key...'),
            'EXTRACTING_HANDWRITING': (50, 'Extracting text from student answer sheet...'),
            'GENERATING': (75, 'Evaluating student response against rubric...'),
            'FINALIZING': (95, 'Recording awarded marks and feedback...'),
            'COMPLETED': (100, 'Grading completed successfully!')
        },
        'document_processing': {
            'PREPARING': (10, 'Preparing document...'),
            'READING_DOCUMENT': (35, 'Extracting text content...'),
            'CHUNKING': (60, 'Chunking text for indexing...'),
            'INDEXING': (85, 'Generating vector embeddings & FAISS index...'),
            'COMPLETED': (100, 'Document processed successfully!')
        }
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskTracker, cls).__new__(cls)
            cls._tasks = {}
        return cls._instance

    def create_task(self, task_type: str, title: str = "Processing AI Task") -> str:
        """Initializes a new task record and returns a unique task_id."""
        task_id = str(uuid.uuid4())
        stage_info = self.STAGE_MAP.get(task_type, {}).get('PREPARING', (5, 'Preparing task...'))
        
        self._tasks[task_id] = {
            'task_id': task_id,
            'task_type': task_type,
            'title': title,
            'status': TaskState.RUNNING,
            'progress': stage_info[0],
            'stage': 'PREPARING',
            'stage_label': stage_info[1],
            'message': stage_info[1],
            'error': None,
            'created_at': time.time(),
            'updated_at': time.time()
        }
        logger.info(f"TaskTracker: Created task {task_id} ({task_type})")
        return task_id

    def update_stage(self, task_id: str, stage: str, custom_message: Optional[str] = None) -> bool:
        """Updates the current stage, stage label, progress percentage, and message of a task."""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task_type = task['task_type']
        
        type_stages = self.STAGE_MAP.get(task_type, {})
        if stage in type_stages:
            progress_pct, default_label = type_stages[stage]
        else:
            progress_pct = task['progress']
            default_label = stage.replace('_', ' ').title()

        task['status'] = TaskState.RUNNING
        task['stage'] = stage
        task['progress'] = progress_pct
        task['stage_label'] = default_label
        task['message'] = custom_message if custom_message else default_label
        task['updated_at'] = time.time()
        
        logger.info(f"TaskTracker: Updated task {task_id} -> Stage: {stage} ({progress_pct}%)")
        return True

    def complete_task(self, task_id: str, message: str = "Task completed successfully.", redirect_url: Optional[str] = None) -> bool:
        """Marks a task as COMPLETED at 100%."""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task['status'] = TaskState.COMPLETED
        task['progress'] = 100
        task['stage'] = 'COMPLETED'
        task['stage_label'] = 'Completed'
        task['message'] = message
        if redirect_url:
            task['redirect_url'] = redirect_url
        task['updated_at'] = time.time()
        logger.info(f"TaskTracker: Completed task {task_id}")
        return True

    def fail_task(self, task_id: str, error_message: str = "Task execution failed.") -> bool:
        """Marks a task as FAILED with a user-friendly error message."""
        if task_id not in self._tasks:
            return False

        task = self._tasks[task_id]
        task['status'] = TaskState.FAILED
        task['stage'] = 'FAILED'
        task['stage_label'] = 'Failed'
        task['error'] = error_message
        task['message'] = error_message
        task['updated_at'] = time.time()
        logger.error(f"TaskTracker: Failed task {task_id}: {error_message}")
        return True

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves task progress data."""
        return self._tasks.get(task_id)

    def clean_old_tasks(self, max_age_seconds: int = 3600):
        """Purges completed/failed tasks older than max_age_seconds."""
        now = time.time()
        to_delete = [
            tid for tid, tdata in self._tasks.items()
            if now - tdata['updated_at'] > max_age_seconds
        ]
        for tid in to_delete:
            del self._tasks[tid]
