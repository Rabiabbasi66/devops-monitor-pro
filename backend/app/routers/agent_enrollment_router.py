import secrets
from datetime import datetime, timedelta

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException

from ..config import settings
from ..models.agent_enrollment import (
    AgentEnrollment,
    EnrollmentCreateResponse,
    EnrollmentRequest,
    EnrollmentResponse,
    generate_enrollment_token,
    hash_token,
)
from ..models.server import Server
from ..models.user import User, UserRole
from ..services.server_service import ServerService
from ..utils.security import get_current_active_user

router = APIRouter(prefix="/agents", tags=["Agent Enrollment"])
server_service = ServerService()


@router.post(
    "/{server_id}/enrollment",
    response_model=EnrollmentCreateResponse,
    summary="Generate enrollment token",
)
async def create_enrollment_token(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Generate a short-lived enrollment token for agent installation."""

    # Verify server ownership
    server = await server_service.get_server(server_id, current_user)

    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Generate token
    enrollment_token = generate_enrollment_token()
    token_hash = hash_token(enrollment_token)

    # Set expiration
    expires_at = datetime.utcnow() + timedelta(minutes=20)

    # Create enrollment record
    enrollment = AgentEnrollment(
        server_id=server_id,
        user_id=str(current_user.id),
        token_hash=token_hash,
        expires_at=expires_at,
    )

    await enrollment.insert()

    return EnrollmentCreateResponse(
        enrollment_token=enrollment_token,
        server_id=server_id,
        api_url=f"{settings.BACKEND_URL.rstrip('/')}/api",
        expires_at=expires_at,
    )


@router.post(
    "/enroll",
    response_model=EnrollmentResponse,
    summary="Enroll agent using enrollment token",
)
async def enroll_agent(request: EnrollmentRequest):
    """Enroll an agent using an enrollment token."""

    enrollment_token = request.enrollment_token
    token_hash = hash_token(enrollment_token)

    # Find valid enrollment
    enrollment = await AgentEnrollment.find_one(
        AgentEnrollment.token_hash == token_hash,
        AgentEnrollment.used == False,
    )

    if not enrollment:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired enrollment token",
        )

    # Check expiration
    if datetime.utcnow() > enrollment.expires_at:
        raise HTTPException(
            status_code=401,
            detail="Enrollment token has expired",
        )

    # Verify server still exists
    try:
        server_oid = PydanticObjectId(enrollment.server_id)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Enrollment record has an invalid server ID",
        )
    server = await Server.get(server_oid)

    if not server:
        raise HTTPException(
            status_code=404,
            detail="Server not found",
        )

    # Generate permanent agent token
    agent_token = secrets.token_urlsafe(32)

    # Update server with agent token
    server.agent_token = agent_token
    server.agent_status = "active"
    server.updated_at = datetime.utcnow()

    await server.save()

    # Mark enrollment as used
    enrollment.used = True
    enrollment.used_at = datetime.utcnow()

    await enrollment.save()

    return EnrollmentResponse(
        server_id=enrollment.server_id,
        agent_token=agent_token,
        api_url=f"{settings.BACKEND_URL.rstrip('/')}/api",
        interval_seconds=30,
    )


@router.delete("/{server_id}/enrollment", summary="Revoke all enrollment tokens")
async def revoke_enrollment_tokens(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Revoke all unused enrollment tokens for a server."""
    server = await server_service.get_server(server_id, current_user)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    deleted_count = await AgentEnrollment.find(
        AgentEnrollment.server_id == server_id,
        AgentEnrollment.used == False,
    ).delete()

    return {"success": True, "revoked_tokens": deleted_count}