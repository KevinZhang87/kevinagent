import json
import logging
import re
from typing import Optional
from sqlalchemy import select

from app.models.database import Skill, async_session
from app.llm.registry import get_provider
from app.llm.base import LLMMessage
import app.config as cfg

logger = logging.getLogger("kevin_agent.skills.evolver")


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from ```json ... ``` block
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try extracting first { ... } block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


class SkillEvolver:
    """Handles skill evolution - improving skills based on usage patterns."""

    def __init__(self, tenant_id: str = None):
        self.tenant_id = tenant_id

    def _get_threshold(self) -> int:
        """Get the evolve threshold from config (auto_evolve) or default."""
        try:
            return cfg.tools_config.skills.evolve_threshold
        except Exception:
            return 3

    async def evolve_skill(self, skill_name: str) -> Optional[dict]:
        """Evolve a skill based on its recorded failure contexts.

        Uses the failure_notes stored during record_usage to give the LLM
        real examples of what went wrong, enabling targeted improvements.
        """
        async with async_session() as session:
            query = select(Skill).where(Skill.name == skill_name)
            if self.tenant_id:
                query = query.where(Skill.tenant_id == self.tenant_id)
            result = await session.execute(query)
            skill = result.scalar_one_or_none()
            if not skill:
                return None

            # Parse real failure contexts
            failure_contexts = []
            if skill.failure_notes:
                try:
                    failure_contexts = json.loads(skill.failure_notes)
                except Exception:
                    failure_contexts = []

            logger.info("Evolving skill: %s v%d (success=%d fail=%d failures_stored=%d)",
                         skill_name, skill.version, skill.success_count,
                         skill.fail_count, len(failure_contexts))

            # Build failure examples for the LLM
            failure_text = ""
            if failure_contexts:
                examples = []
                for i, fc in enumerate(failure_contexts[-5:], 1):
                    parts = [f"Failure {i}:"]
                    if fc.get("q"):
                        parts.append(f"  User asked: {fc['q']}")
                    if fc.get("o"):
                        parts.append(f"  Skill output: {fc['o']}")
                    if fc.get("e"):
                        parts.append(f"  Error: {fc['e']}")
                    examples.append("\n".join(parts))
                failure_text = "\n\n".join(examples)
            else:
                failure_text = f"No specific failure data recorded. The skill has {skill.fail_count} failures out of {skill.success_count + skill.fail_count} total uses."

            # Use LLM to improve the skill
            provider = cfg.default_provider
            model = cfg.default_model
            llm = get_provider(provider, model)

            prompt = json.dumps({
                "skill_name": skill.name,
                "current_instruction": skill.instruction,
                "failure_analysis": failure_text,
            }, ensure_ascii=False)

            response = await llm.chat([
                LLMMessage(role="system", content="""You are a skill optimizer. Your job is to improve an AI agent's skill instruction based on real failure data.

The skill has a current instruction and a list of actual failure cases (what users asked, what the skill produced, and what went wrong).

Analyze the failures and improve the instruction to:
1. Address the specific patterns that caused failures
2. Add guardrails for edge cases that tripped up the skill
3. Clarify ambiguous steps
4. Keep the core purpose intact

CRITICAL: Return ONLY a JSON object (no markdown, no explanation outside the JSON):
{
    "instruction": "<the complete improved instruction text>",
    "changes": "<brief description of what you changed and why>"
}"""),
                LLMMessage(role="user", content=prompt),
            ])

            data = _extract_json(response.content)
            if not data:
                logger.warning("Skill evolution failed for %s: LLM did not return valid JSON. Raw: %s",
                               skill_name, response.content[:200])
                return None

            if "instruction" not in data:
                logger.warning("Skill evolution failed for %s: missing 'instruction' in response. Keys: %s",
                               skill_name, list(data.keys()))
                return None

            skill.instruction = data["instruction"]
            skill.version += 1
            # Reset counters and failure notes after evolution
            skill.fail_count = 0
            skill.success_count = 0
            skill.failure_notes = None
            await session.commit()

            changes = data.get("changes", "No changes described")
            logger.info("Skill evolved: %s -> v%d changes=%s",
                         skill_name, skill.version, changes[:100])
            return {
                "name": skill.name,
                "version": skill.version,
                "changes": changes,
            }

    async def auto_evolve(self):
        """Automatically evolve skills with poor performance.

        Uses the configurable threshold (default 3) to decide which skills
        need evolution. Skills must have fail_count > threshold AND
        fail_count > success_count.
        """
        threshold = self._get_threshold()
        async with async_session() as session:
            query = select(Skill).where(
                Skill.is_active == True,
                Skill.fail_count > threshold,
                Skill.fail_count > Skill.success_count,
            )
            if self.tenant_id:
                query = query.where(Skill.tenant_id == self.tenant_id)
            result = await session.execute(query)
            skills = result.scalars().all()

            if not skills:
                logger.info("No skills need evolution (threshold=%d)", threshold)
                return []

            logger.info("Auto-evolving %d skills (threshold=%d)", len(skills), threshold)

            evolved = []
            for skill in skills:
                result = await self.evolve_skill(skill.name)
                if result:
                    evolved.append(result)

            return evolved
