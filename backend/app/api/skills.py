import logging
import re
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models.schemas import SkillCreate, SkillUpdate
from app.skills.manager import SkillManager
from app.skills.evolver import SkillEvolver

logger = logging.getLogger("kevin_agent.skills")

router = APIRouter(prefix="/api/skills", tags=["skills"])
skill_manager = SkillManager()
skill_evolver = SkillEvolver()


def parse_markdown_skill(text: str) -> dict | None:
    """Parse a Markdown skill file with YAML-like frontmatter.

    Supported format:
    ---
    name: skill_name
    description: Skill description
    ---

    # Instruction

    Step-by-step instructions...
    """
    text = text.strip()
    if not text:
        return None

    # Try to extract YAML frontmatter (between --- delimiters)
    frontmatter = {}
    body = text

    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', text, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1).strip()
        body = fm_match.group(2).strip()

        # Parse simple YAML key: value pairs
        for line in fm_text.split('\n'):
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                frontmatter[key.strip()] = value.strip().strip('"').strip("'")

    # Extract name from frontmatter or first heading
    name = frontmatter.get('name', '')
    description = frontmatter.get('description', '')

    if not name:
        # Try to get name from first heading
        heading_match = re.search(r'^#\s+(.+)$', body, re.MULTILINE)
        if heading_match:
            name = heading_match.group(1).strip()
            # Convert heading to snake_case
            name = re.sub(r'[^\w]+', '_', name.lower()).strip('_')

    # The instruction is the body content (excluding the title heading if it matches the name)
    instruction = body
    if name and instruction.startswith(f'# {name}'):
        # Remove the title heading, keep the rest
        instruction = re.sub(r'^#\s+.+?\n', '', instruction, count=1).strip()

    # Also try alternate heading: "## Instruction" section
    instruction_match = re.search(r'^##\s+Instruction\s*\n(.*)$', instruction, re.MULTILINE | re.DOTALL)
    if instruction_match:
        instruction = instruction_match.group(1).strip()

    if not name:
        return None

    # Generate a description from frontmatter or first paragraph
    if not description:
        first_para = re.search(r'^(?!#)(.+?)(?:\n\n|\n#|$)', instruction, re.MULTILINE | re.DOTALL)
        if first_para:
            description = first_para.group(1).strip()[:200]
        else:
            description = name.replace('_', ' ').title()

    return {
        "name": name,
        "description": description,
        "instruction": instruction,
    }


class MarkdownImportRequest(BaseModel):
    content: str
    overwrite: bool = False


class SkillTestRequest(BaseModel):
    name: str
    test_input: str = ""


class SkillImportItem(BaseModel):
    name: str
    description: str
    instruction: str
    version: Optional[int] = None


class SkillImportRequest(BaseModel):
    skills: list[SkillImportItem]
    overwrite: bool = False


@router.get("")
async def list_skills():
    """List all skills."""
    skills = await skill_manager.list_skills()
    return {"skills": skills}


@router.post("")
async def create_skill(request: SkillCreate):
    """Create a new skill."""
    logger.info("Creating skill: %s", request.name)
    skill = await skill_manager.create_skill(
        name=request.name,
        description=request.description,
        instruction=request.instruction,
    )
    return skill


@router.get("/{name}")
async def get_skill(name: str):
    """Get a specific skill."""
    skill = await skill_manager.get_skill(name)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.put("/{name}")
async def update_skill(name: str, request: SkillUpdate):
    """Update a skill."""
    logger.info("Updating skill: %s", name)
    success = await skill_manager.update_skill(
        name=name,
        description=request.description,
        instruction=request.instruction,
        is_active=request.is_active,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"status": "updated"}


@router.delete("/{name}")
async def delete_skill(name: str):
    """Delete (deactivate) a skill."""
    logger.info("Deleting skill: %s", name)
    success = await skill_manager.update_skill(name=name, is_active=False)
    if not success:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"status": "deleted"}


@router.post("/evolve")
async def evolve_skills():
    """Trigger automatic skill evolution."""
    logger.info("Triggering skill evolution")
    results = await skill_evolver.auto_evolve()
    logger.info("Evolution complete: %d skills evolved", len(results))
    return {"evolved": results}


@router.post("/test")
async def test_skill(request: SkillTestRequest):
    """Test a skill by getting its context."""
    skill = await skill_manager.get_skill(request.name)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    context = await skill_manager.get_skill_context(request.test_input or request.name)
    return {"skill": skill, "context": context}


@router.post("/import")
async def import_skills(request: SkillImportRequest):
    """Import skills from JSON data. Supports batch import with optional overwrite."""
    results = {"imported": [], "skipped": [], "errors": []}
    for item in request.skills:
        try:
            # Check if skill already exists
            existing = await skill_manager.get_skill(item.name)
            if existing and not request.overwrite:
                results["skipped"].append({"name": item.name, "reason": "already exists"})
                continue
            if existing and request.overwrite:
                # Update existing skill
                await skill_manager.update_skill(
                    name=item.name,
                    instruction=item.instruction,
                    is_active=True,
                )
                results["imported"].append({"name": item.name, "action": "updated"})
            else:
                # Create new skill
                await skill_manager.create_skill(
                    name=item.name,
                    description=item.description,
                    instruction=item.instruction,
                )
                results["imported"].append({"name": item.name, "action": "created"})
        except Exception as e:
            results["errors"].append({"name": item.name, "error": str(e)})

    logger.info("Skills import: %d imported, %d skipped, %d errors",
                len(results["imported"]), len(results["skipped"]), len(results["errors"]))
    return results


@router.get("/export/all")
async def export_skills():
    """Export all skills as JSON data for backup or sharing."""
    skills = await skill_manager.list_skills()
    return {"skills": skills, "version": "1.0"}


@router.post("/import/markdown")
async def import_markdown_skill(request: MarkdownImportRequest):
    """Import a skill from Markdown format with optional YAML frontmatter.

    Format:
    ---
    name: skill_name
    description: Skill description
    ---

    # Instruction
    Step-by-step instructions...
    """
    parsed = parse_markdown_skill(request.content)
    if not parsed:
        raise HTTPException(status_code=400, detail="Could not parse Markdown skill. Need a 'name' in frontmatter or a heading.")

    try:
        existing = await skill_manager.get_skill(parsed["name"])
        if existing and not request.overwrite:
            return {"status": "skipped", "reason": "already exists", "name": parsed["name"]}

        if existing and request.overwrite:
            await skill_manager.update_skill(
                name=parsed["name"],
                instruction=parsed["instruction"],
                is_active=True,
            )
            return {"status": "updated", "name": parsed["name"], "description": parsed["description"]}
        else:
            await skill_manager.create_skill(
                name=parsed["name"],
                description=parsed["description"],
                instruction=parsed["instruction"],
            )
            return {"status": "created", "name": parsed["name"], "description": parsed["description"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
