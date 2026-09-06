from fastapi import APIRouter, Depends

from ..models.user import User, UserRole
from ..schemas.auth import UserResponse
from ..utils.security import get_current_admin_user

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(current_user: User = Depends(get_current_admin_user)):
    users = await User.find().to_list()
    return [
        UserResponse(
            id=str(u.id),
            email=str(u.email),
            username=u.username,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            is_verified=u.is_verified,
            created_at=u.created_at,
        )
        for u in users
    ]
