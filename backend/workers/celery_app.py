"""
Celery application for background tasks.

Tasks:
- PDF ingestion (process_manual_task)
- Pricing refresh (refresh_pricing_task)
- Email notifications (send_email_task)
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Exchange, Queue
import logging
from backend.config.config import settings

logger = logging.getLogger(__name__)


# CELERY APP CONFIGURATION
broker_url = settings.get_celery_broker_url()
backend_url = settings.get_celery_backend()

logger.info(f"Connecting to Celery broker: {broker_url.split('@')[-1] if broker_url and '@' in broker_url else broker_url}")
logger.info(f"Connecting to Celery backend: {backend_url.split('@')[-1] if backend_url and '@' in backend_url else backend_url}")

app = Celery("pedalbot",
            broker=broker_url,
            backend=backend_url,
            include=[
                "backend.workers.ingest_worker",
                "backend.workers.pricing_worker",
                "backend.workers.email_worker"
            ]
            )

# Configuration
app.conf.update(
    # Task routing
    task_routes={
        # Ingestion tasks
        "ingest_manual": {"queue": "ingestion"},
        "cleanup_old_jobs": {"queue": "ingestion"},
        "batch_ingest_manuals": {"queue": "ingestion"},
        
        # Pricing tasks
        "refresh_pricing": {"queue": "pricing"},
        "refresh_all_pricing": {"queue": "pricing"},
        "check_price_alerts": {"queue": "pricing"},
        
        # Email tasks
        "send_email": {"queue": "notifications"},
        "send_welcome_email": {"queue": "notifications"},
        "send_manual_processed_email": {"queue": "notifications"},
        "send_price_alert_email": {"queue": "notifications"},
        "send_bulk_emails": {"queue": "notifications"},
    },

    task_default_queue="default",

    # Task serialization
    task_serializer= "json",
    accept_content= ["json"],
    result_serializer= "json",

    # Timezone
    timezone='UTC',
    enable_utc=True,

    # Task execution
    task_acks_late = True,  # Acknowledge after task completes
    task_reject_on_worker_lost= True,
    worker_prefetch_multiplier=1,  # One task at a time for heavy tasks

    # Result backend
    result_expires=3600,  # 1 hour
    
    # Error handling - Increased for OCR processing (Google Vision is slow)
    task_soft_time_limit=1800,  # 30 minutes soft limit
    task_time_limit=3600,  # 60 minutes hard limit
    
    # Retry policy
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
)

# Define Queues
app.conf.task_queues = (
    Queue("default", Exchange("default"), routing_key="default"),
    Queue("ingestion", Exchange("ingestion"), routing_key="ingestion.#"),
    Queue("pricing", Exchange("pricing"), routing_key="pricing.#"),
    Queue("notifications", Exchange("notifications"), routing_key="notifications.#")
)

# Periodic tasks
app.conf.beat_schedule = {
    # Refresh pricing for all pedals daily at 2 AM

    "refresh-all-pricing": {
        "task": "backend.workers.pricing_worker.refresh_all_pricing_task",
        "schedule": crontab(hour=2, minute=0),
    },

    # Clean up old job records weekly
    "cleanup-old-jobs": {
        "task": "backend.workers.ingest_worker.cleanup_old_jobs",
        "schedule": crontab(day_of_week=1, hour=3, minute=0)
    }
}


# TASK BASE CLASS
class BaseTask(app.Task):
    """Base task class with common functionality."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handler for failed tasks."""
        logger.error(
            f"Task {self.name} failed: {exc}",
            extra={
                "task_id": task_id,
                "task_args": args,
                "task_kwargs": kwargs,
            },
        )


    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handler for task retries."""

        logger.warning(
            f"Task {self.name} retrying: {exc}",
            extra={
                'task_id': task_id,
                'retry': self.request.retries,
            }
        )


    def on_success(self, retval, task_id, args, kwargs):
        """Handler for successful tasks."""
        logger.info(
            f"Task {self.name} completed successfully",
            extra={'task_id': task_id}
        )     


# HEALTH CHECK
@app.task(name='celery.ping', bind=True)
def ping(self):
    """Health check task."""
    return 'pong'


# STARTUP
if __name__ == '__main__':
    app.start()
