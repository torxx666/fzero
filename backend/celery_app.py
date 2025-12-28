import os
from celery import Celery
from loguru import logger

# Configuration Redis
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

# Initialisation de Celery
# On le nomme 'tasks' pour correspondre au fichier tasks.py que nous allons créer
celery = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Configuration optionnelle
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Paris',
    enable_utc=True,
    # Désactivation du "rate limit" pour les tests
    worker_prefetch_multiplier=1,
)

logger.info(f"Celery | Configured with broker: {REDIS_URL}")
