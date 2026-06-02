"""Pydantic schemas for auth requests and responses."""

from pydantic import BaseModel
from typing import Optional
from dataclasses import dataclass


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None  # Tenant name, defaults to email prefix


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: str
    user_id: str
    role: str


class UserInfo(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    role: str
    tenant_name: str
    plan: str


@dataclass
class TenantContext:
    """Tenant context injected into request handlers via FastAPI Depends()."""
    tenant_id: str
    user_id: str
    role: str
