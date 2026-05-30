import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.models.database import UserSettings, async_session

logger = logging.getLogger("kevin_agent.settings")

router = APIRouter(prefix="/api/user-settings", tags=["user-settings"])


class SettingUpdate(BaseModel):
    key: str
    value: str


class BatchSettingUpdate(BaseModel):
    settings: dict[str, str]


@router.get("")
async def get_all_settings():
    """Get all user settings."""
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(select(UserSettings))
        settings = {}
        for s in result.scalars():
            settings[s.key] = s.value
        return {"settings": settings}


@router.get("/{key}")
async def get_setting(key: str):
    """Get a specific setting by key."""
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(UserSettings).where(UserSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            return {"key": key, "value": setting.value}
        return {"key": key, "value": ""}


@router.put("")
async def update_settings(request: BatchSettingUpdate):
    """Batch update user settings."""
    from sqlalchemy import select
    async with async_session() as session:
        for key, value in request.settings.items():
            result = await session.execute(
                select(UserSettings).where(UserSettings.key == key)
            )
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                setting = UserSettings(key=key, value=value)
                session.add(setting)
        await session.commit()
    return {"status": "ok"}
