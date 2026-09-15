import logging
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException

from ..models.notification_settings import NotificationChannelConfig, NotificationProviderType
from ..models.user import User
from ..schemas.notification_settings import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    ProviderStatusResponse,
    TestNotificationRequest,
    EmailVerificationRequest,
    EmailVerificationVerifyRequest,
    EmailVerificationResponse,
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
    """Send a test notification through a specific provider."""
    recipient = request.recipient

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


@router.get(
    "/providers/status",
    response_model=ProviderStatusResponse,
    summary="Get platform provider availability",
)
async def get_provider_status(
    current_user: User = Depends(get_current_active_user),
):
    """Report which platform notification providers are configured."""
    return {"providers": notification_service.get_provider_status()}


@router.post("/email/request-verification", response_model=EmailVerificationResponse, summary="Request email verification")
async def request_email_verification(
    request: EmailVerificationRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Request a verification code for the provided email address."""
    result = await notification_service.request_email_verification(
        user_id=str(current_user.id),
        email=request.email
    )
    return result


@router.post("/email/verify", response_model=EmailVerificationResponse, summary="Verify email code")
async def verify_email_code(
    request: EmailVerificationVerifyRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Verify the email using the provided code."""
    result = await notification_service.verify_email_code(
        user_id=str(current_user.id),
        email=request.email,
        code=request.code
    )
    return result