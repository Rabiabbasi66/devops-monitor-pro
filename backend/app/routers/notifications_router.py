from fastapi import APIRouter, Depends, HTTPException

from ..models.user import User
from ..schemas.notification import NotificationListResponse, NotificationResponse
from ..services.notification_service import NotificationService
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])
notification_service = NotificationService()


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_active_user),
):
    items = await notification_service.list_for_user(str(current_user.id), unread_only)
    unread = sum(1 for n in items if not n.read)
    return NotificationListResponse(
        items=[
            NotificationResponse(
                id=str(n.id),
                user_id=n.user_id,
                alert_id=n.alert_id,
                type=n.type,
                title=n.title,
                message=n.message,
                read=n.read,
                created_at=n.created_at,
            )
            for n in items
        ],
        total=len(items),
        unread=unread,
    )


@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
):
    notification = await notification_service.mark_read(
        notification_id, str(current_user.id)
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationResponse(
        id=str(notification.id),
        user_id=notification.user_id,
        alert_id=notification.alert_id,
        type=notification.type,
        title=notification.title,
        message=notification.message,
        read=notification.read,
        created_at=notification.created_at,
    )
