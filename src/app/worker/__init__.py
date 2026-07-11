import structlog
from arq import create_pool
from arq.connections import RedisSettings
from src.app.config import settings

logger = structlog.get_logger()

async def enqueue_task(task_name: str, *args, **kwargs) -> None:
    """
    Utility helper to safely queue jobs into the Redis arq worker.
    """
    try:
        redis_settings = RedisSettings(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT
        )
        pool = await create_pool(redis_settings)
        await pool.enqueue_job(task_name, *args, **kwargs)
        await pool.close()
    except Exception as e:
        logger.error("failed_to_enqueue_background_task", task=task_name, error=str(e))
