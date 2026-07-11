import asyncio
import structlog
from arq.connections import RedisSettings
from src.app.config import settings

logger = structlog.get_logger()

async def send_booking_notification(ctx, patient_email: str, doctor_name: str, start_time_str: str) -> None:
    logger.info("sending_booking_notification_started", email=patient_email, doctor=doctor_name)
    # Simulate network delay for SMTP/SMS API
    await asyncio.sleep(0.5)
    logger.info("sending_booking_notification_completed", email=patient_email)

async def generate_prescription_pdf(ctx, prescription_id: str) -> None:
    logger.info("generating_prescription_pdf_started", prescription_id=prescription_id)
    # Simulate complex cryptographic signing and PDF generation IO
    await asyncio.sleep(0.8)
    logger.info("generating_prescription_pdf_completed", prescription_id=prescription_id)

async def run_compliance_check(ctx, user_id: str, action: str) -> None:
    logger.info("compliance_audit_job_started", user_id=user_id, action=action)
    await asyncio.sleep(0.2)
    logger.info("compliance_audit_job_completed", user_id=user_id)

# Worker configuration class for arq CLI runner
class WorkerSettings:
    functions = [send_booking_notification, generate_prescription_pdf, run_compliance_check]
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT
    )
