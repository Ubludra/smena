"""Passkey-protected Safe password change.

A MAX notification is informational, never an authorization. The only
password-change authority is a fresh WebAuthn assertion by the previously
enrolled credential with user verification (PIN/biometrics).

Enrollment requires knowledge of the existing Safe password; a stolen MAX
access token or an unlocked Safe token alone cannot enroll a new credential.
Passkeys can be synced across devices by their provider, so WebAuthn alone
cannot prove a physical phone was used. The UI guides enrollment on a phone.
"""

import base64
import datetime as dt
import json
import logging
import secrets
from typing import Annotated, Any, cast

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from smena_api.api.deps import get_app_settings, get_current_user, get_session
from smena_api.api.routes.safe import check_safe_password_attempt, hash_safe_password
from smena_api.db.models import SafePasskey, User
from smena_api.integrations.max_bot import send_safe_change_alert

router = APIRouter(prefix="/safe/security", tags=["safe-security"])
logger = logging.getLogger(__name__)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]
CEREMONY_TTL = dt.timedelta(minutes=5)
REQUEST_TTL = dt.timedelta(minutes=5)
REQUEST_COOLDOWN = dt.timedelta(minutes=1)


class EnrollStartIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=4, max_length=128)


class CredentialIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    credential: dict[str, Any]


class ChangeFinishIn(CredentialIn):
    new_password: str = Field(min_length=8, max_length=128)


class SecurityStatus(BaseModel):
    registered: bool
    pending_change: bool
    configured: bool


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _configuration(request: Request) -> tuple[str, str]:
    settings = get_app_settings(request)
    rp_id, origin = settings.passkey_rp_id, settings.passkey_origin
    if not rp_id or not origin:
        raise HTTPException(503, "Защита ключом устройства ещё не настроена")
    return rp_id, origin


async def _lock_user(session: AsyncSession, user_id: Any) -> User:
    return (
        await session.execute(select(User).where(User.id == user_id).with_for_update())
    ).scalar_one()


async def _row(session: AsyncSession, user: User) -> SafePasskey:
    record = await session.get(SafePasskey, user.id, with_for_update=True)
    if record is None:
        record = SafePasskey(user_id=user.id, sign_count=0)
        session.add(record)
        await session.flush()
    return record


def _clear_challenge(record: SafePasskey) -> None:
    record.challenge = None
    record.challenge_kind = None
    record.challenge_expires = None


def _valid_challenge(record: SafePasskey, kind: str) -> bytes:
    if (
        record.challenge_kind != kind
        or record.challenge is None
        or record.challenge_expires is None
        or record.challenge_expires <= _now()
    ):
        raise HTTPException(403, "Подтверждение истекло. Начните заново")
    return _unb64(record.challenge)


@router.get("/status", response_model=SecurityStatus)
async def security_status(
    user: UserDep, session: SessionDep, request: Request
) -> SecurityStatus:
    record = await session.get(SafePasskey, user.id)
    now = _now()
    return SecurityStatus(
        registered=record is not None and record.credential_id is not None,
        pending_change=bool(
            record is not None
            and record.pending_change_id
            and record.pending_change_expires
            and record.pending_change_expires > now
        ),
        configured=bool(
            get_app_settings(request).passkey_rp_id
            and get_app_settings(request).passkey_origin
        ),
    )


@router.post("/enroll/options")
async def enroll_options(
    body: EnrollStartIn, user: UserDep, session: SessionDep, request: Request
) -> dict[str, Any]:
    rp_id, _ = _configuration(request)
    locked_user = await _lock_user(session, user.id)
    record = await _row(session, locked_user)
    if record.credential_id is not None:
        raise HTTPException(409, "Доверенный ключ уже зарегистрирован")
    if not await check_safe_password_attempt(
        password=body.current_password, user=locked_user, session=session
    ):
        raise HTTPException(403, "Неверный пароль Сейфа")
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name="Смена",
        user_id=locked_user.id.bytes,
        user_name=locked_user.max_user_id,
        user_display_name=locked_user.display_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    record.challenge = _b64(options.challenge)
    record.challenge_kind = "enroll"
    record.challenge_expires = _now() + CEREMONY_TTL
    await session.commit()
    return cast(dict[str, Any], json.loads(options_to_json(options)))


@router.post("/enroll/finish")
async def enroll_finish(
    body: CredentialIn, user: UserDep, session: SessionDep, request: Request
) -> dict[str, bool]:
    rp_id, origin = _configuration(request)
    await _lock_user(session, user.id)
    record = await _row(session, user)
    if record.credential_id is not None:
        raise HTTPException(409, "Доверенный ключ уже зарегистрирован")
    challenge = _valid_challenge(record, "enroll")
    # A failed attempt burns the challenge. The client must restart.
    _clear_challenge(record)
    await session.flush()
    try:
        result = verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            require_user_verification=True,
        )
    except Exception as exc:
        logger.info("safe_passkey_registration_rejected")
        await session.commit()
        raise HTTPException(403, "Не удалось проверить ключ устройства") from exc
    record.credential_id = _b64(result.credential_id)
    record.public_key = _b64(result.credential_public_key)
    record.sign_count = result.sign_count
    await session.commit()
    logger.info("safe_passkey_registered")
    return {"registered": True}


@router.post("/change/request")
async def change_request(
    user: UserDep, session: SessionDep, request: Request
) -> dict[str, bool]:
    _configuration(request)
    settings = get_app_settings(request)
    if settings.environment == "production" and (
        not user.max_user_id.isdecimal() or settings.max_bot_token is None
    ):
        raise HTTPException(503, "Уведомления MAX недоступны")
    await _lock_user(session, user.id)
    record = await _row(session, user)
    if record.credential_id is None:
        raise HTTPException(409, "Сначала зарегистрируйте доверенный телефон")
    now = _now()
    if record.pending_change_expires and record.pending_change_expires > now:
        raise HTTPException(409, "Запрос уже ожидает подтверждения")
    if record.last_request_at and now - record.last_request_at < REQUEST_COOLDOWN:
        raise HTTPException(
            429, "Повторите через минуту", headers={"Retry-After": "60"}
        )
    record.pending_change_id = secrets.token_urlsafe(24)
    record.pending_change_expires = now + REQUEST_TTL
    record.last_request_at = now
    _clear_challenge(record)
    if settings.environment == "production":
        try:
            bot_token = settings.max_bot_token
            if bot_token is None:
                raise HTTPException(503, "Уведомления MAX недоступны")
            await send_safe_change_alert(
                bot_token=bot_token.get_secret_value(),
                max_user_id=user.max_user_id,
            )
        except httpx.HTTPError:
            await session.rollback()
            logger.warning("safe_change_alert_delivery_failed")
            raise HTTPException(
                502, "Не удалось доставить уведомление MAX. Откройте чат с ботом и повторите."
            ) from None
    await session.commit()
    logger.info("safe_change_requested")
    return {"pending": True}


@router.post("/change/options")
async def change_options(
    user: UserDep, session: SessionDep, request: Request
) -> dict[str, Any]:
    rp_id, _ = _configuration(request)
    await _lock_user(session, user.id)
    record = await _row(session, user)
    if (
        record.credential_id is None
        or record.pending_change_id is None
        or record.pending_change_expires is None
        or record.pending_change_expires <= _now()
    ):
        raise HTTPException(409, "Нет действующего запроса смены пароля")
    options = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=_unb64(record.credential_id))
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    record.challenge = _b64(options.challenge)
    record.challenge_kind = "change"
    record.challenge_expires = _now() + CEREMONY_TTL
    await session.commit()
    return cast(dict[str, Any], json.loads(options_to_json(options)))


@router.post("/change/finish")
async def change_finish(
    body: ChangeFinishIn, user: UserDep, session: SessionDep, request: Request
) -> dict[str, bool]:
    rp_id, origin = _configuration(request)
    locked_user = await _lock_user(session, user.id)
    record = await _row(session, locked_user)
    if (
        record.credential_id is None
        or record.public_key is None
        or record.pending_change_id is None
        or record.pending_change_expires is None
        or record.pending_change_expires <= _now()
    ):
        raise HTTPException(409, "Запрос смены пароля истёк")
    challenge = _valid_challenge(record, "change")
    _clear_challenge(record)
    await session.flush()
    try:
        verified = verify_authentication_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=_unb64(record.public_key),
            credential_current_sign_count=record.sign_count,
            require_user_verification=True,
        )
        if verified.credential_id != _unb64(record.credential_id):
            raise ValueError("unexpected credential")
    except Exception as exc:
        await session.commit()
        logger.info("safe_change_assertion_rejected")
        raise HTTPException(403, "Подтверждение ключом устройства не прошло") from exc
    record.sign_count = verified.new_sign_count
    locked_user.safe_password_hash = hash_safe_password(body.new_password)
    locked_user.safe_password_version += 1
    record.pending_change_id = None
    record.pending_change_expires = None
    await session.commit()
    logger.info("safe_password_changed_with_passkey")
    return {"changed": True}
