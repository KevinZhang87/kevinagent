"""Auth service: password hashing, JWT encode/decode, user/tenant CRUD."""

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from sqlalchemy import select

from app.models.database import async_session
from app.auth.models import Tenant, User

logger = logging.getLogger("kevin_agent.auth")

# JWT config — MUST be set via environment variable in production
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = uuid.uuid4().hex
    logger.warning("JWT_SECRET not set! Generated random secret (tokens will be invalid on restart). "
                    "Set JWT_SECRET in .env for production use.")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "72"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    data["iat"] = datetime.now(timezone.utc)
    return jwt.encode(data, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


async def register_user(email: str, password: str, name: str = None) -> dict:
    """Register a new user with a new tenant. Returns token info or raises."""
    async with async_session() as session:
        # Check if email already exists
        result = await session.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            raise ValueError("Email already registered")

        tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        tenant_name = name or email.split("@")[0]

        tenant = Tenant(tenant_id=tenant_id, name=tenant_name)
        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            password_hash=hash_password(password),
            role="owner",
        )
        session.add(tenant)
        session.add(user)
        await session.commit()

        logger.info("User registered: email=%s tenant=%s", email, tenant_id)
        return {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": "owner",
        }


async def login_user(email: str, password: str) -> dict:
    """Authenticate user. Returns token info or raises."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid email or password")
        if not user.is_active:
            raise ValueError("Account is disabled")

        logger.info("User logged in: email=%s tenant=%s", email, user.tenant_id)
        return {
            "tenant_id": user.tenant_id,
            "user_id": user.user_id,
            "role": user.role,
        }


async def get_user_info(user_id: str) -> dict | None:
    """Get user and tenant info."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return None

        tenant_result = await session.execute(
            select(Tenant).where(Tenant.tenant_id == user.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

        return {
            "user_id": user.user_id,
            "tenant_id": user.tenant_id,
            "email": user.email,
            "role": user.role,
            "tenant_name": tenant.name if tenant else "",
            "plan": tenant.plan if tenant else "free",
        }
