"""Auth API endpoints: register, login, me."""

import logging
from fastapi import APIRouter, HTTPException

from app.auth.schema import RegisterRequest, LoginRequest, TokenResponse, UserInfo
from app.auth.service import register_user, login_user, get_user_info, create_token
from app.auth.dependencies import get_current_tenant
from app.auth.schema import TenantContext
from fastapi import Depends

logger = logging.getLogger("kevin_agent.auth.router")

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Register a new user and tenant."""
    try:
        info = await register_user(request.email, request.password, request.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = create_token({
        "tenant_id": info["tenant_id"],
        "user_id": info["user_id"],
        "role": info["role"],
    })

    return TokenResponse(
        access_token=token,
        tenant_id=info["tenant_id"],
        user_id=info["user_id"],
        role=info["role"],
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate and get a token."""
    try:
        info = await login_user(request.email, request.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    token = create_token({
        "tenant_id": info["tenant_id"],
        "user_id": info["user_id"],
        "role": info["role"],
    })

    return TokenResponse(
        access_token=token,
        tenant_id=info["tenant_id"],
        user_id=info["user_id"],
        role=info["role"],
    )


@router.get("/me", response_model=UserInfo)
async def get_me(ctx: TenantContext = Depends(get_current_tenant)):
    """Get current user info."""
    info = await get_user_info(ctx.user_id)
    if not info:
        raise HTTPException(status_code=404, detail="User not found")
    return UserInfo(**info)
