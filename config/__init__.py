"""
config/__init__.py
──────────────────
Importing the Celery app here ensures it is loaded when Django starts,
so that shared_task decorators across all apps work correctly.
"""
from .celery import app as celery_app

__all__ = ("celery_app",)
