import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.models.schemas import AgentCreate, AgentNode, AgentEdge, WorkflowSnapshot
from app.core.agent import agent_manager
from app.models.database import async_session, AgentState

logger = logging.getLogger("kevin_agent.agents")

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentUpdateRequest(BaseModel):
    model: Optional[str] = None
    provider: Optional[str] = None
    parent_agent_id: Optional[str] = None


@router.get("")
async def list_agents():
    """List all agents and their states. Always includes main agent."""
    states = await agent_manager.get_all_agent_states()
    # Ensure main agent is always in the list
    if not any(s["agent_id"] == "main" for s in states):
        from app.config import default_provider, default_model
        states.insert(0, {
            "agent_id": "main",
            "status": "idle",
            "current_task": "",
            "model": default_model,
            "provider": default_provider,
            "parent_agent_id": None,
        })
    return {"agents": states}


@router.post("")
async def create_agent(request: AgentCreate):
    """Create a new sub-agent."""
    logger.info("Creating agent: name=%s provider=%s model=%s", request.name, request.provider, request.model)
    # Use the user-provided name as agent_id for human-readable display
    agent_id = request.name.strip().replace(" ", "_").lower() if request.name else ""
    agent = await agent_manager.create_agent(
        agent_id=agent_id,
        provider=request.provider,
        model=request.model,
        parent_agent_id=request.parent_agent_id,
    )
    return {"agent_id": agent.agent_id, "status": "created"}


@router.get("/workflow")
async def get_workflow():
    """Get the current agent workflow for visualization."""
    states = await agent_manager.get_all_agent_states()

    # Ensure main agent is always in the list
    if not any(s["agent_id"] == "main" for s in states):
        from app.config import default_provider, default_model
        states.insert(0, {
            "agent_id": "main",
            "status": "idle",
            "current_task": "",
            "model": default_model,
            "provider": default_provider,
            "parent_agent_id": None,
        })

    agents = []
    edges = []

    for i, state in enumerate(states):
        agents.append(AgentNode(
            id=state["agent_id"],
            name=state["agent_id"].replace("_", " ").title(),
            status=state["status"],
            model=state.get("model", ""),
            provider=state.get("provider", ""),
            current_task=state.get("current_task"),
            position={"x": 250 * (i % 3), "y": 150 * (i // 3)},
            parent_agent_id=state.get("parent_agent_id"),
        ))

        if state.get("parent_agent_id"):
            edges.append(AgentEdge(
                id=f"{state['parent_agent_id']}-{state['agent_id']}",
                source=state["parent_agent_id"],
                target=state["agent_id"],
                label="spawned",
                animated=state["status"] != "idle",
            ))

    return WorkflowSnapshot(agents=agents, edges=edges)


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get a specific agent's state."""
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        # Auto-create agent from database or with defaults
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(
                select(AgentState).where(AgentState.agent_id == agent_id)
            )
            state = result.scalar_one_or_none()
        if state:
            agent = await agent_manager.create_agent(
                agent_id=state.agent_id,
                provider=state.provider,
                model=state.model,
            )
        elif agent_id == "main":
            from app.config import default_provider, default_model
            agent = await agent_manager.create_agent(
                agent_id="main",
                provider=default_provider,
                model=default_model,
            )
        else:
            raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "agent_id": agent.agent_id,
        "status": agent.status,
        "current_task": agent.current_task,
        "model": agent.model,
        "provider": agent.provider_name,
        "session_id": agent.session_id,
    }


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, request: AgentUpdateRequest):
    """Update an agent's configuration (model, provider)."""
    agent = agent_manager.get_agent(agent_id)
    if not agent:
        # Auto-create agent from database or with defaults (same logic as chat API)
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(
                select(AgentState).where(AgentState.agent_id == agent_id)
            )
            state = result.scalar_one_or_none()
        if state:
            agent = await agent_manager.create_agent(
                agent_id=state.agent_id,
                provider=state.provider,
                model=state.model,
            )
        elif agent_id == "main":
            from app.config import default_provider, default_model
            agent = await agent_manager.create_agent(
                agent_id="main",
                provider=default_provider,
                model=default_model,
            )
        else:
            raise HTTPException(status_code=404, detail="Agent not found")

    # Update in-memory agent
    if request.provider is not None or request.model is not None:
        new_provider = request.provider or agent.provider_name
        new_model = request.model or agent.model
        if new_provider != agent.provider_name or new_model != agent.model:
            from app.llm.registry import get_provider
            agent.provider_name = new_provider
            agent.model = new_model
            agent.llm = get_provider(new_provider, new_model)

    # Update in database
    from sqlalchemy import update as sql_update
    async with async_session() as session:
        updates = {}
        if request.provider is not None:
            updates["provider"] = request.provider
        if request.model is not None:
            updates["model"] = request.model
        if request.parent_agent_id is not None:
            updates["parent_agent_id"] = request.parent_agent_id
        if updates:
            await session.execute(
                sql_update(AgentState).where(AgentState.agent_id == agent_id).values(**updates)
            )
            await session.commit()

    logger.info("Agent updated: %s -> provider=%s model=%s", agent_id, request.provider, request.model)
    return {
        "agent_id": agent_id,
        "status": "updated",
        "provider": agent.provider_name,
        "model": agent.model,
    }


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete (stop) an agent. Cannot delete main agent."""
    if agent_id == "main":
        raise HTTPException(status_code=400, detail="Cannot delete main agent")

    # Remove from in-memory dict
    agent_manager._agents.pop(agent_id, None)

    # Also remove from database
    from sqlalchemy import delete as sql_delete
    async with async_session() as session:
        await session.execute(sql_delete(AgentState).where(AgentState.agent_id == agent_id))
        await session.commit()

    logger.info("Agent deleted: %s", agent_id)
    return {"status": "deleted"}
