"""
config/celery.py
────────────────
Celery application entry point for Col Realty.

Worker startup (run from project root):
    celery -A config worker -l info -Q default,hubspot

Beat scheduler (for periodic tasks like MLS sync):
    celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
"""
import os
from celery import Celery
from celery.utils.log import get_task_logger

# Tell Celery which Django settings module to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("colrealty")

# Pull all CELERY_* settings from Django settings.py
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in every INSTALLED_APP
app.autodiscover_tasks()

logger = get_task_logger(__name__)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Sanity-check task — run with: celery -A config call config.celery.debug_task"""
    logger.info(f"Request: {self.request!r}")
