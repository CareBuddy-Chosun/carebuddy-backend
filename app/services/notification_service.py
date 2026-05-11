import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_guardian_sms(
    guardian_phone: str, user_name: str
) -> bool:
    """Send emergency SMS to a guardian via Twilio."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning("Twilio not configured, skipping SMS")
        return False

    message_body = (
        f"CareBuddy has detected a potential emergency situation for {user_name}. "
        "Please check on them immediately."
    )

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message_body,
            from_=settings.TWILIO_FROM_NUMBER,
            to=guardian_phone,
        )
        return True
    except Exception:
        logger.exception("Failed to send guardian SMS to %s", guardian_phone)
        return False
