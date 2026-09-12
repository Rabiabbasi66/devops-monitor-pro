import logging
import secrets as _secrets
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

from ..config import settings
from ..models.notification_settings import NotificationChannelConfig, NotificationProviderType
from ..models.user import User
from ..schemas.notification_settings import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    ProviderStatusResponse,
    TelegramConnectResponse,
    TelegramConnectStatusResponse,
    TelegramDisconnectResponse,
    TestNotificationRequest,
)
from ..services.notification_service import NotificationService
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/notifications/settings", tags=["Notification Settings"])
notification_service = NotificationService()
logger = logging.getLogger("devops_monitor")


def _channel_response(channel: NotificationChannelConfig) -> NotificationChannelResponse:
    """Build a safe channel response (never includes platform secrets)."""
    return NotificationChannelResponse(
        id=str(channel.id),
        user_id=channel.user_id,
        provider=channel.provider,
        enabled=channel.enabled,
        recipient=channel.recipient,
        min_severity=channel.min_severity,
        notification_types=channel.notification_types,
        cooldown_seconds=channel.cooldown_seconds,
        last_sent_at=channel.last_sent_at,
        provider_metadata=channel.provider_metadata or {},
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


@router.get("/", response_model=List[NotificationChannelResponse], summary="List notification channels")
async def list_notification_channels(
    current_user: User = Depends(get_current_active_user),
):
    """Get all notification channels for the current user."""
    channels = await notification_service.get_user_channels(str(current_user.id))
    return [_channel_response(channel) for channel in channels]


@router.post("/", response_model=NotificationChannelResponse, summary="Create notification channel")
async def create_notification_channel(
    channel_data: NotificationChannelCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Create a new notification channel (recipient validated per provider)."""
    validation_error = notification_service.validate_recipient_for_provider(
        channel_data.provider, channel_data.recipient
    )
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    channel = await notification_service.create_notification_channel(
        user_id=str(current_user.id),
        channel_data=channel_data.model_dump()
    )
    return _channel_response(channel)


@router.put("/{channel_id}", response_model=NotificationChannelResponse, summary="Update notification channel")
async def update_notification_channel(
    channel_id: str,
    update_data: NotificationChannelUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update a notification channel (ownership enforced)."""
    try:
        oid = PydanticObjectId(channel_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid channel ID format")

    channel = await NotificationChannelConfig.get(oid)
    if not channel or channel.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Notification channel not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    if "recipient" in update_dict:
        validation_error = notification_service.validate_recipient_for_provider(
            channel.provider, update_dict["recipient"]
        )
        if validation_error:
            raise HTTPException(status_code=400, detail=validation_error)

    updated = await notification_service.update_notification_channel(
        channel,
        update_dict
    )
    return _channel_response(updated)


@router.delete("/{channel_id}", summary="Delete notification channel")
async def delete_notification_channel(
    channel_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a notification channel."""
    try:
        oid = PydanticObjectId(channel_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid channel ID format")

    channel = await NotificationChannelConfig.get(oid)
    if not channel or channel.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Notification channel not found")
    
    await notification_service.delete_notification_channel(channel)
    return {"success": True, "message": "Notification channel deleted"}


@router.post("/test", summary="Send test notification")
async def send_test_notification(
    request: TestNotificationRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Send a test notification through a specific provider.

    ``recipient`` is optional: when omitted (or when ``channel_id`` is given),
    the user's own saved channel for that provider is used. Ownership of the
    channel is always validated.
    """
    recipient = request.recipient

    # Ownership: a channel_id must belong to the caller
    if request.channel_id:
        channel = await notification_service.get_user_channel(
            str(current_user.id), request.channel_id
        )
        if not channel:
            raise HTTPException(status_code=404, detail="Notification channel not found")
        if channel.provider != request.provider:
            raise HTTPException(status_code=400, detail="Provider does not match the channel")
        recipient = channel.recipient

    if not recipient:
        # Fall back to the user's own saved channel for this provider
        channels = await notification_service.get_user_channels(str(current_user.id))
        match = next((c for c in channels if c.provider == request.provider), None)
        if match:
            recipient = match.recipient

    if not recipient:
        raise HTTPException(status_code=400, detail="Recipient is required")

    result = await notification_service.send_test_notification(
        user_id=str(current_user.id),
        provider=request.provider,
        recipient=recipient
    )
    
    if result["success"]:
        return {"success": True, "message": "Test notification sent successfully", "details": result}
    else:
        return {"success": False, "message": "Failed to send test notification", "details": result}


# ----------------------------------------------------------------------
# Platform provider availability (safe, no secrets)
# ----------------------------------------------------------------------

@router.get(
    "/providers/status",
    response_model=ProviderStatusResponse,
    summary="Get platform provider availability",
)
async def get_provider_status(
    current_user: User = Depends(get_current_active_user),
):
    """Report which platform notification providers are configured.

    Returns booleans and static messages only - never provider credentials -
    so the frontend can show "Platform configuration unavailable" without
    exposing environment values.
    """
    return {"providers": notification_service.get_provider_status()}


# ----------------------------------------------------------------------
# Telegram connection flow (platform-managed bot)
# ----------------------------------------------------------------------

@router.post(
    "/telegram/connect",
    response_model=TelegramConnectResponse,
    summary="Start Telegram connection",
)
async def start_telegram_connection(
    current_user: User = Depends(get_current_active_user),
):
    """Create a one-time connection token and a t.me deep link.

    The token expires and is single-use; the raw token is shown once and only
    its hash is stored server-side.
    """
    result = await notification_service.create_telegram_connect_token(str(current_user.id))
    if not result.get("success"):
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "Telegram provider is not available"),
        )
    return result


@router.get(
    "/telegram/connect/status",
    response_model=TelegramConnectStatusResponse,
    summary="Check Telegram connection status",
)
async def telegram_connection_status(
    token: str,
    current_user: User = Depends(get_current_active_user),
):
    """Poll whether the current user's connection token has been used by the bot."""
    return await notification_service.get_telegram_connect_status(str(current_user.id), token)


@router.delete(
    "/telegram/disconnect",
    response_model=TelegramDisconnectResponse,
    summary="Disconnect Telegram",
)
async def disconnect_telegram(
    current_user: User = Depends(get_current_active_user),
):
    """Remove the current user's Telegram channel(s)."""
    return await notification_service.disconnect_telegram(str(current_user.id))


@router.post("/telegram/webhook", summary="Telegram webhook (platform bot updates)")
async def telegram_webhook(request: Request):
    """Receive Telegram bot updates (public endpoint called by Telegram).

    When ``TELEGRAM_WEBHOOK_SECRET`` is configured, the
    ``X-Telegram-Bot-Api-Secret-Token`` header must match. Handles
    ``/start <token>`` messages to complete one-time connection tokens,
    mapping the Telegram chat_id to the DevOps Monitor user.
    """
    if settings.TELEGRAM_WEBHOOK_SECRET:
        header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not _secrets.compare_digest(header_secret, settings.TELEGRAM_WEBHOOK_SECRET):
            raise HTTPException(status_code=403, detail="Forbidden")

    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    message = update.get("message") or update.get("edited_message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    from_user = message.get("from") or {}
    username = from_user.get("username")

    if text.startswith("/start") and chat_id:
        parts = text.split(maxsplit=1)
        raw_token = parts[1].strip() if len(parts) > 1 else ""
        if raw_token:
            result = await notification_service.complete_telegram_connect(
                raw_token, str(chat_id), username
            )
            # Log the outcome factually; never echo the token contents
            logger.info(
                "Telegram webhook connection attempt: success=%s",
                result.get("success"),
            )

    # Always acknowledge to Telegram (no enumeration feedback)
    return {"ok": True}