import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select

from app.models.database import UserSettings, async_session
from app.auth.dependencies import get_current_tenant
from app.auth.schema import TenantContext

logger = logging.getLogger("kevin_agent.settings")

router = APIRouter(prefix="/api/user-settings", tags=["user-settings"])


class SettingUpdate(BaseModel):
    key: str
    value: str


class BatchSettingUpdate(BaseModel):
    settings: dict[str, str]


@router.get("")
async def get_all_settings(ctx: TenantContext = Depends(get_current_tenant)):
    """Get all user settings for this tenant."""
    async with async_session() as session:
        result = await session.execute(select(UserSettings).where(UserSettings.tenant_id == ctx.tenant_id))
        settings = {}
        for s in result.scalars():
            settings[s.key] = s.value
        return {"settings": settings}


@router.get("/{key}")
async def get_setting(key: str, ctx: TenantContext = Depends(get_current_tenant)):
    """Get a specific setting by key."""
    async with async_session() as session:
        result = await session.execute(
            select(UserSettings).where(UserSettings.key == key, UserSettings.tenant_id == ctx.tenant_id)
        )
        setting = result.scalar_one_or_none()
        if setting:
            return {"key": key, "value": setting.value}
        return {"key": key, "value": ""}


@router.put("")
async def update_settings(request: BatchSettingUpdate, ctx: TenantContext = Depends(get_current_tenant)):
    """Batch update user settings."""
    async with async_session() as session:
        for key, value in request.settings.items():
            result = await session.execute(
                select(UserSettings).where(UserSettings.key == key, UserSettings.tenant_id == ctx.tenant_id)
            )
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                setting = UserSettings(key=key, value=value, tenant_id=ctx.tenant_id)
                session.add(setting)
        await session.commit()
    return {"status": "ok"}
