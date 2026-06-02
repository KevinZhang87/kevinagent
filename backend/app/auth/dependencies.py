"""FastAPI dependency for tenant context injection."""

import logging
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.auth.service import decode_token
from app.auth.schema import TenantContext

logger = logging.getLogger("kevin_agent.auth.dep")

security = HTTPBearer(auto_error=False)


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TenantContext:
    """Extract and validate tenant context from JWT token.

    This is the core dependency that all protected endpoints use.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception as e:
        logger.warning("Invalid token: %s", e)
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    tenant_id = payload.get("tenant_id")
    user_id = payload.get("user_id")
    role = payload.get("role", "member")

    if not tenant_id or not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    return TenantContext(tenant_id=tenant_id, user_id=user_id, role=role)
