from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("buscomipana", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_eager_propagates=True,
    timezone="UTC",
    beat_schedule={
        "retry-failed-sms": {"task": "retry_failed_sms", "schedule": 300.0},
        "cleanup-expired-otps": {"task": "cleanup_expired_otps", "schedule": 3600.0},
    },
)

celery_app.autodiscover_tasks(["app.workers"])
