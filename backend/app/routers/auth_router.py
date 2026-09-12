from datetime import datetime

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..models.audit_log import AuditAction, AuditLog
from ..models.user import User, UserRole
from ..schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from ..utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    existing_email = await User.find_one({"email": user_data.email})
    if existing_email:
        raise HTTPException(status_code=409, detail="Email already registered")

    existing_username = await User.find_one({"username": user_data.username})
    if existing_username:
        raise HTTPException(status_code=409, detail="Username already taken")

    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        role=UserRole.USER,
        is_active=True,
        is_verified=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await new_user.insert()

    user_response = UserResponse(
        id=str(new_user.id),
        email=str(new_user.email),
        username=new_user.username,
        full_name=new_user.full_name,
        role=new_user.role,
        is_active=new_user.is_active,
        is_verified=new_user.is_verified,
        created_at=new_user.created_at,
    )
    return {
        "success": True,
        "message": "User registered successfully",
        "user": user_response.model_dump(),
    }


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, request: Request):
    user = await User.find_one({"email": login_data.email})
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    user.last_login = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    await user.save()

    await AuditLog(
        user_id=str(user.id),
        action=AuditAction.LOGIN,
        resource_type="user",
        resource_id=str(user.id),
        ip_address=request.client.host if request.client else None,
    ).insert()

    token_data = {"sub": str(user.id), "email": str(user.email), "role": user.role.value}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshTokenRequest):
    payload = decode_token(body.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Ensure this is actually a refresh token, not an access token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail="Invalid token type: refresh token required",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user = await User.get(PydanticObjectId(user_id))
    except Exception:
        user = None

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    token_data = {"sub": str(user.id), "email": str(user.email), "role": user.role.value}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        email=str(current_user.email),
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
    )
