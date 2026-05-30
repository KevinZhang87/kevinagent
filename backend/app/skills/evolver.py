import json
import logging
from typing import Optional
from sqlalchemy import select

from app.models.database import Skill, async_session
from app.llm.registry import get_provider
from app.llm.base import LLMMessage
from app.config import default_provider, default_model

logger = logging.getLogger("kevin_agent.skills.evolver")


class SkillEvolver:
    """Handles skill evolution - improving skills based on usage patterns."""

    async def evolve_skill(self, skill_name: str, recent_failures: list[str]) -> Optional[dict]:
        """Evolve a skill based on recent failures."""
        async with async_session() as session:
            result = await session.execute(
                select(Skill).where(Skill.name == skill_name)
            )
            skill = result.scalar_one_or_none()
            if not skill:
                return None

            logger.info("Evolving skill: %s v%d (success=%d fail=%d)",
                         skill_name, skill.version, skill.success_count, skill.fail_count)

            # Use LLM to improve the skill
            provider = default_provider
            model = default_model
            llm = get_provider(provider, model)
            response = await llm.chat([
                LLMMessage(role="system", content="""You are a skill optimizer. Given a skill's current instruction and recent failure cases,
improve the instruction to handle these cases better. Keep the core purpose but make it more robust.

Return a JSON object with:
- instruction: the improved instruction
- changes: brief description of what changed"""),
                LLMMessage(role="user", content=json.dumps({
                    "current_instruction": skill.instruction,
                    "failures": recent_failures[:5],
                })),
            ])

            try:
                data = json.loads(response.content)
                skill.instruction = data["instruction"]
                skill.version += 1
                # Reset counters after evolution
                skill.fail_count = 0
                await session.commit()
                logger.info("Skill evolved: %s -> v%d changes=%s",
                             skill_name, skill.version, data.get("changes", ""))
                return {
                    "name": skill.name,
                    "version": skill.version,
                    "changes": data.get("changes", ""),
                }
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Skill evolution failed for %s: %s", skill_name, e)
                return None

    async def auto_evolve(self):
        """Automatically evolve skills with poor performance."""
        async with async_session() as session:
            result = await session.execute(
                select(Skill).where(
                    Skill.is_active == True,
                    Skill.fail_count > 3,
                    Skill.fail_count > Skill.success_count,
                )
            )
            skills = result.scalars().all()

            if not skills:
                logger.info("No skills need evolution")
                return []

            logger.info("Auto-evolving %d skills", len(skills))

            evolved = []
            for skill in skills:
                result = await self.evolve_skill(skill.name, [f"Skill has {skill.fail_count} failures"])
                if result:
                    evolved.append(result)

            return evolved
