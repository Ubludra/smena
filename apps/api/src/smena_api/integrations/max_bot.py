"""Send an informational alert via MAX; MAX chat buttons never authorize a change."""

import logging

import httpx

logger = logging.getLogger(__name__)


async def send_safe_change_alert(*, bot_token: str, max_user_id: str) -> None:
    """Notify the MAX account. Approval requires a separate WebAuthn assertion."""
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(
            "https://platform-api2.max.ru/messages",
            params={"user_id": max_user_id},
            headers={"Authorization": bot_token},
            json={
                "text": (
                    "Смена: запрошена смена пароля Сейфа. "
                    "Если это вы, откройте «Смену» на своём доверенном телефоне "
                    "и подтвердите действие ключом устройства в течение 5 минут. "
                    "Никакие кнопки в этом чате не меняют пароль. "
                    "Если запрос чужой — проигнорируйте его."
                ),
            },
        )
        response.raise_for_status()
    logger.info("safe_change_alert_sent")
