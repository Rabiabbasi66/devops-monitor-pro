from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from ..models.notification_settings import NotificationChannelConfig, NotificationProviderType
from ..models.user import User
from ..schemas.notification_settings import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
    TestNotificationRequest,
)
from ..services.notification_service import NotificationService
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/notifications/settings", tags=["Notification Settings"])
notification_service = NotificationService()


@router.get("/", response_model=List[NotificationChannelResponse], summary="List notification channels")
async def list_notification_channels(
    current_user: User = Depends(get_current_active_user),
):
    """Get all notification channels for the current user."""
    channels = await notification_service.get_user_channels(str(current_user.id))
    return [
        NotificationChannelResponse(
            id=str(channel.id),
            user_id=channel.user_id,
            provider=channel.provider,
            enabled=channel.enabled,
            recipient=channel.recipient,
            min_severity=channel.min_severity,
            notification_types=channel.notification_types,
            cooldown_seconds=channel.cooldown_seconds,
            last_sent_at=channel.last_sent_at,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )
        for channel in channels
    ]


@router.post("/", response_model=NotificationChannelResponse, summary="Create notification channel")
async def create_notification_channel(
    channel_data: NotificationChannelCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Create a new notification channel."""
    channel = await notification_service.create_notification_channel(
        user_id=str(current_user.id),
        channel_data=channel_data.model_dump()
    )
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
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


@router.put("/{channel_id}", response_model=NotificationChannelResponse, summary="Update notification channel")
async def update_notification_channel(
    channel_id: str,
    update_data: NotificationChannelUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update a notification channel."""
    channel = await NotificationChannelConfig.get(channel_id)
    if not channel or channel.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="Notification channel not found")
    
    updated = await notification_service.update_notification_channel(
        channel,
        update_data.model_dump(exclude_unset=True)
    )
    
    return NotificationChannelResponse(
        id=str(updated.id),
        user_id=updated.user_id,
        provider=updated.provider,
        enabled=updated.enabled,
        recipient=updated.recipient,
        min_severity=updated.min_severity,
        notification_types=updated.notification_types,
        cooldown_seconds=updated.cooldown_seconds,
        last_sent_at=updated.last_sent_at,
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.delete("/{channel_id}", summary="Delete notification channel")
async def delete_notification_channel(
    channel_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a notification channel."""
    channel = await NotificationChannelConfig.get(channel_id)
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
    result = await notification_service.send_test_notification(
        user_id=str(current_user.id),
        provider=request.provider,
        recipient=request.recipient
    )
    
    if result["success"]:
        return {"success": True, "message": "Test notification sent successfully", "details": result}
    else:
        return {"success": False, "message": "Failed to send test notification", "details": result}