import json
import os
import logging
from typing import Optional
from sqlalchemy import select, desc

from app.models.database import Skill, Message, async_session
from app.llm.registry import get_provider
from app.llm.base import LLMMessage
import app.config as cfg

logger = logging.getLogger("kevin_agent.skills.manager")

# Base directory for agent workspaces
WORKSPACES_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "workspaces")


class SkillManager:
    """Manages skills - creation, storage, retrieval, and evolution."""

    def __init__(self, agent_id: str = None):
        """Initialize SkillManager, optionally scoped to a specific agent.

        Args:
            agent_id: If provided, skills are stored in workspaces/{agent_id}/skills/
        """
        self.agent_id = agent_id
        self._skills_dir = None
        if agent_id:
            self._skills_dir = os.path.join(WORKSPACES_BASE, agent_id, "skills")
            os.makedirs(self._skills_dir, exist_ok=True)

    def _get_skill_file_path(self, name: str) -> str:
        """Get the file path for a skill JSON file."""
        return os.path.join(self._skills_dir, f"{name}.json")

    def _save_skill_to_file(self, name: str, data: dict):
        """Save skill data to a JSON file in the agent's skills directory."""
        if not self._skills_dir:
            return
        try:
            filepath = self._get_skill_file_path(name)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug("Skill saved to file: %s", filepath)
        except Exception as e:
            logger.warning("Failed to save skill to file: %s", e)

    def _load_skill_from_file(self, name: str) -> Optional[dict]:
        """Load skill data from a JSON file."""
        if not self._skills_dir:
            return None
        try:
            filepath = self._get_skill_file_path(name)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning("Failed to load skill from file: %s", e)
        return None

    async def create_skill(self, name: str, description: str, instruction: str) -> dict:
        async with async_session() as session:
            # Check for duplicate name
            result = await session.execute(
                select(Skill).where(Skill.name == name)
            )
            if result.scalar_one_or_none():
                raise ValueError(f"Skill '{name}' already exists")

            skill = Skill(
                name=name,
                description=description,
                instruction=instruction,
            )
            session.add(skill)
            await session.commit()
            await session.refresh(skill)
            logger.info("Skill created: %s v%d", name, skill.version)

            # Also save to agent's skills directory if agent_id is set
            skill_data = {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "instruction": skill.instruction,
                "version": skill.version,
                "is_active": True,
                "success_count": 0,
                "fail_count": 0,
            }
            self._save_skill_to_file(name, skill_data)

            return skill_data

    async def get_skill(self, name: str) -> Optional[dict]:
        async with async_session() as session:
            result = await session.execute(
                select(Skill).where(Skill.name == name, Skill.is_active == True)
            )
            skill = result.scalar_one_or_none()
            if not skill:
                return None
            return {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "instruction": skill.instruction,
                "success_count": skill.success_count,
                "fail_count": skill.fail_count,
                "version": skill.version,
                "is_active": skill.is_active,
                "created_at": skill.created_at.isoformat(),
                "updated_at": skill.updated_at.isoformat(),
            }

    async def list_skills(self, include_inactive: bool = False) -> list[dict]:
        async with async_session() as session:
            query = select(Skill)
            if not include_inactive:
                query = query.where(Skill.is_active == True)
            result = await session.execute(
                query.order_by(desc(Skill.updated_at))
            )
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "instruction": s.instruction,
                    "success_count": s.success_count,
                    "fail_count": s.fail_count,
                    "version": s.version,
                    "is_active": s.is_active,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in result.scalars()
            ]

    async def update_skill(self, name: str, description: Optional[str] = None, instruction: Optional[str] = None, is_active: Optional[bool] = None) -> bool:
        async with async_session() as session:
            result = await session.execute(
                select(Skill).where(Skill.name == name)
            )
            skill = result.scalar_one_or_none()
            if not skill:
                return False
            if description is not None:
                skill.description = description
                logger.info("Skill description updated: %s", name)
            if instruction is not None:
                skill.instruction = instruction
                skill.version += 1
                logger.info("Skill updated: %s -> v%d", name, skill.version)
            if is_active is not None:
                skill.is_active = is_active
                logger.info("Skill %s: is_active=%s", name, is_active)
            await session.commit()

            # Also update in agent's skills directory if agent_id is set
            if self._skills_dir:
                self._save_skill_to_file(name, {
                    "name": name,
                    "description": skill.description,
                    "instruction": skill.instruction,
                    "version": skill.version,
                    "is_active": skill.is_active,
                    "success_count": skill.success_count,
                    "fail_count": skill.fail_count,
                })

            return True

    async def record_usage(self, name: str, success: bool, context: dict = None):
        """Record skill usage, optionally storing failure context for evolution.

        Args:
            name: Skill name
            success: Whether the skill was used successfully
            context: Optional dict with 'user_query', 'skill_output', 'error' for failure analysis
        """
        async with async_session() as session:
            result = await session.execute(
                select(Skill).where(Skill.name == name)
            )
            skill = result.scalar_one_or_none()
            if skill:
                if success:
                    skill.success_count += 1
                else:
                    skill.fail_count += 1
                    # Store failure context for future evolution
                    if context:
                        import json as _json
                        notes = []
                        if skill.failure_notes:
                            try:
                                notes = _json.loads(skill.failure_notes)
                            except Exception:
                                notes = []
                        # Keep last 10 failure entries, each capped at 300 chars
                        entry = {
                            "q": (context.get("user_query") or "")[:300],
                            "o": (context.get("skill_output") or "")[:300],
                            "e": (context.get("error") or "")[:200],
                        }
                        notes.append(entry)
                        skill.failure_notes = _json.dumps(notes[-10:], ensure_ascii=False)
                await session.commit()

    async def try_create_from_conversation(self, session_id: str, response: str):
        """Try to create a skill from a complex conversation."""
        # Check if auto-creation is enabled
        if not cfg.tools_config.skills.auto_create:
            return

        async with async_session() as session:
            # Get recent messages
            result = await session.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.desc())
                .limit(20)
            )
            messages = list(result.scalars())

            if len(messages) < cfg.tools_config.skills.min_messages:
                return  # Too short to be a skill

            # Count tool calls
            tool_count = sum(1 for m in messages if m.role == "tool")
            if tool_count < cfg.tools_config.skills.min_tool_calls:
                return  # Not complex enough

            # Use LLM to summarize as a skill
            conversation_text = "\n".join(
                f"{m.role}: {m.content[:200]}" for m in reversed(messages)
            )

            try:
                provider = cfg.default_provider
                model = cfg.default_model
                llm = get_provider(provider, model)
                logger.info("Attempting to create skill from conversation: session=%s", session_id[:8])
                summary_response = await llm.chat([
                    LLMMessage(role="system", content="""Analyze this conversation and extract a reusable skill.
Return a JSON object with:
- name: short snake_case name for the skill
- description: one-line description
- instruction: detailed step-by-step instruction for how to perform this task

Only create a skill if the conversation shows a clear, reusable pattern. If not, return {"skip": true}."""),
                    LLMMessage(role="user", content=conversation_text[:3000]),
                ])

                data = json.loads(summary_response.content)
                if data.get("skip"):
                    logger.debug("Skill creation skipped: not a reusable pattern")
                    return

                # Check if skill already exists
                existing = await self.get_skill(data["name"])
                if existing:
                    logger.debug("Skill already exists: %s", data["name"])
                    return

                await self.create_skill(
                    name=data["name"],
                    description=data["description"],
                    instruction=data["instruction"],
                )
            except json.JSONDecodeError:
                logger.debug("Skill creation: LLM did not return valid JSON")
            except ValueError as e:
                logger.debug("Skill creation failed: %s", e)
            except Exception as e:
                logger.warning("Skill creation error: %s", e)

    async def get_skill_context(self, query: str) -> tuple[str, list[str]]:
        """Get relevant skills as context for the agent.

        Returns:
            (context_string, list_of_matched_skill_names)
        """
        skills = await self.list_skills()
        if not skills:
            return "", []

        # Simple keyword matching for relevance
        relevant = []
        query_lower = query.lower()
        for skill in skills:
            if any(word in skill["description"].lower() or word in skill["name"].lower()
                   for word in query_lower.split()):
                relevant.append(skill)

        if not relevant:
            # Return top skills by success rate
            relevant = sorted(skills, key=lambda s: s["success_count"], reverse=True)[:3]

        matched_names = [s["name"] for s in relevant[:5]]
        context = "\n\nRelevant skills:\n"
        for s in relevant[:5]:
            context += f"- {s['name']}: {s['description']}\n  Instruction: {s['instruction'][:200]}\n"
        return context, matched_names
