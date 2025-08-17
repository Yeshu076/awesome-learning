from celery import Celery
from celery.schedules import crontab
import os

from app.core.config import settings

# Create Celery instance
celery_app = Celery(
    "linkedin_automation",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.celery.tasks.scraping_tasks",
        "app.celery.tasks.application_tasks",
        "app.celery.tasks.user_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Scheduled tasks
celery_app.conf.beat_schedule = {
    # Scrape jobs every hour for active search profiles
    "scrape-linkedin-jobs": {
        "task": "app.celery.tasks.scraping_tasks.scheduled_job_scraping",
        "schedule": crontab(minute=0),  # Every hour
    },
    # Process auto-applications every 30 minutes
    "process-auto-applications": {
        "task": "app.celery.tasks.application_tasks.process_auto_applications",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    # Clean up old sessions daily
    "cleanup-sessions": {
        "task": "app.celery.tasks.user_tasks.cleanup_old_sessions",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    # Update application statuses every 4 hours
    "update-application-status": {
        "task": "app.celery.tasks.application_tasks.update_application_statuses",
        "schedule": crontab(minute=0, hour="*/4"),  # Every 4 hours
    },
}

celery_app.conf.timezone = "UTC"

if __name__ == "__main__":
    celery_app.start()