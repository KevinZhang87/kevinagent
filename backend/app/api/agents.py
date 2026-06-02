import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.models.schemas import AgentCreate, AgentNode, AgentEdge, WorkflowSnapshot
from app.core.agent import agent_manager
from app.models.database import async_session, AgentState
from app.auth.dependencies import get_current_tenant
from app.auth.schema import TenantContext

logger = logging.getLogger("kevin_agent.agents")

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentUpdateRequest(BaseModel):
    model: Optional[str] = None
    provider: Optional[str] = None
    parent_agent_id: Optional[str] = None
    system_prompt: Optional[str] = None
    description: Optional[str] = None
    capabilities: Optional[list[str]] = None
    tools: Optional[list[str]] = None  # tool whitelist


@router.get("")
async def list_agents(ctx: TenantContext = Depends(get_current_tenant)):
    """List all agents and their states. Always includes main agent."""
    states = await agent_manager.get_all_agent_states(tenant_id=ctx.tenant_id)
    # Ensure main agent is always in the list
    if not any(s["agent_id"] == "main" for s in states):
        import app.config as cfg
        states.insert(0, {
            "agent_id": "main",
            "status": "idle",
            "current_task": "",
            "model": cfg.default_model,
            "provider": cfg.default_provider,
            "parent_agent_id": None,
        })
    return {"agents": states}


@router.post("")
async def create_agent(request: AgentCreate, ctx: TenantContext = Depends(get_current_tenant)):
    """Create a new sub-agent."""
    logger.info("Creating agent: name=%s provider=%s model=%s tenant=%s", request.name, request.provider, request.model, ctx.tenant_id)
    # Use the user-provided name as agent_id for human-readable display
    agent_id = request.name.strip().replace(" ", "_").lower() if request.name else ""
    agent = await agent_manager.create_agent(
        agent_id=agent_id,
        provider=request.provider,
        model=request.model,
        parent_agent_id=request.parent_agent_id,
        system_prompt=request.system_prompt or "",
        tenant_id=ctx.tenant_id,
        description=request.description,
        capabilities=request.capabilities,
        tools=request.tools,
    )
    return {"agent_id": agent.agent_id, "status": "created"}


@router.get("/workflow")
async def get_workflow(ctx: TenantContext = Depends(get_current_tenant)):
    """Get the current agent workflow for visualization."""
    states = await agent_manager.get_all_agent_states(tenant_id=ctx.tenant_id)

    # Ensure main agent is always in the list
    if not any(s["agent_id"] == "main" for s in states):
        import app.config as cfg
        states.insert(0, {
            "agent_id": "main",
            "status": "idle",
            "current_task": "",
            "model": cfg.default_model,
            "provider": cfg.default_provider,
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
            ephemeral=state.get("ephemeral", False),
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
async def get_agent(agent_id: str, ctx: TenantContext = Depends(get_current_tenant)):
    """Get a specific agent's state."""
    agent = agent_manager.get_agent(agent_id, tenant_id=ctx.tenant_id)
    if not agent:
        # Auto-create agent from database or with defaults
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(
                select(AgentState).where(AgentState.agent_id == agent_id, AgentState.tenant_id == ctx.tenant_id)
            )
            state = result.scalar_one_or_none()
        if state:
            agent = await agent_manager.create_agent(
                agent_id=state.agent_id,
                provider=state.provider,
                model=state.model,
                tenant_id=ctx.tenant_id,
            )
        elif agent_id == "main":
            import app.config as cfg
            agent = await agent_manager.create_agent(
                agent_id="main",
                provider=cfg.default_provider,
                model=cfg.default_model,
                tenant_id=ctx.tenant_id,
            )
        else:
            raise HTTPException(status_code=404, detail="Agent not found")
    # Load extended fields from DB
    import json as _json
    description = None
    capabilities = None
    tools_list = None
    system_prompt_val = agent.system_prompt or None
    async with async_session() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(AgentState).where(AgentState.agent_id == agent_id, AgentState.tenant_id == ctx.tenant_id)
        )
        state = result.scalar_one_or_none()
        if state:
            description = state.description
            capabilities = _json.loads(state.capabilities) if state.capabilities else None
            tools_list = _json.loads(state.tools) if state.tools else None
            system_prompt_val = system_prompt_val or state.system_prompt

    return {
        "agent_id": agent.agent_id,
        "status": agent.status,
        "current_task": agent.current_task,
        "model": agent.model,
        "provider": agent.provider_name,
        "session_id": agent.session_id,
        "system_prompt": system_prompt_val,
        "description": description,
        "capabilities": capabilities,
        "tools": tools_list,
    }


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, request: AgentUpdateRequest, ctx: TenantContext = Depends(get_current_tenant)):
    """Update an agent's configuration (model, provider)."""
    agent = agent_manager.get_agent(agent_id, tenant_id=ctx.tenant_id)
    if not agent:
        # Auto-create agent from database or with defaults (same logic as chat API)
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(
                select(AgentState).where(AgentState.agent_id == agent_id, AgentState.tenant_id == ctx.tenant_id)
            )
            state = result.scalar_one_or_none()
        if state:
            agent = await agent_manager.create_agent(
                agent_id=state.agent_id,
                provider=state.provider,
                model=state.model,
                tenant_id=ctx.tenant_id,
            )
        elif agent_id == "main":
            import app.config as cfg
            agent = await agent_manager.create_agent(
                agent_id="main",
                provider=cfg.default_provider,
                model=cfg.default_model,
                tenant_id=ctx.tenant_id,
            )
        else:
            raise HTTPException(status_code=404, detail="Agent not found")

    # Update in-memory agent
    if request.provider is not None or request.model is not None:
        new_provider = request.provider or agent.provider_name
        new_model = request.model or agent.model
        # Normalize model name: strip "provider/" prefix
        if "/" in new_model:
            new_model = new_model.split("/", 1)[1]
        if new_provider != agent.provider_name or new_model != agent.model:
            from app.llm.registry import get_provider
            agent.provider_name = new_provider
            agent.model = new_model
            agent.llm = get_provider(new_provider, new_model)
    if request.system_prompt is not None:
        agent.system_prompt = request.system_prompt

    # Update in database (scoped to tenant)
    from sqlalchemy import update as sql_update
    import json as _json
    async with async_session() as session:
        updates = {}
        if request.provider is not None:
            updates["provider"] = request.provider
        if request.model is not None:
            updates["model"] = request.model
        if request.parent_agent_id is not None:
            updates["parent_agent_id"] = request.parent_agent_id
        if request.system_prompt is not None:
            updates["system_prompt"] = request.system_prompt
        if request.description is not None:
            updates["description"] = request.description
        if request.capabilities is not None:
            updates["capabilities"] = _json.dumps(request.capabilities)
        if request.tools is not None:
            updates["tools"] = _json.dumps(request.tools)
        if updates:
            await session.execute(
                sql_update(AgentState).where(
                    AgentState.agent_id == agent_id,
                    AgentState.tenant_id == ctx.tenant_id,
                ).values(**updates)
            )
            await session.commit()

    logger.info("Agent updated: %s -> provider=%s model=%s", agent_id, request.provider, request.model)
    return {
        "agent_id": agent_id,
        "status": "updated",
        "provider": agent.provider_name,
        "model": agent.model,
    }


@router.post("/{agent_id}/cancel")
async def cancel_agent(agent_id: str, ctx: TenantContext = Depends(get_current_tenant)):
    """Cancel an in-flight agent chat() execution."""
    agent = agent_manager.get_agent(agent_id, tenant_id=ctx.tenant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status not in ("thinking", "executing"):
        return {"status": "not_running", "message": f"Agent is in '{agent.status}' state, nothing to cancel"}
    agent.cancel()
    logger.info("Cancel requested for agent %s (tenant=%s)", agent_id, ctx.tenant_id)
    return {"status": "cancel_requested", "agent_id": agent_id}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, ctx: TenantContext = Depends(get_current_tenant)):
    """Delete (stop) an agent. Cannot delete main agent."""
    if agent_id == "main":
        raise HTTPException(status_code=400, detail="Cannot delete main agent")

    # Check if agent exists (in memory or DB)
    agent = agent_manager.get_agent(agent_id, tenant_id=ctx.tenant_id)
    db_exists = False
    if not agent:
        from sqlalchemy import select
        async with async_session() as session:
            result = await session.execute(
                select(AgentState).where(AgentState.agent_id == agent_id, AgentState.tenant_id == ctx.tenant_id)
            )
            db_exists = result.scalar_one_or_none() is not None
        if not db_exists:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    # Remove from in-memory dict (tenant-scoped)
    tenant_agents = agent_manager.get_tenant_agents(ctx.tenant_id)
    tenant_agents.pop(agent_id, None)
    agent_manager._agents.pop(agent_id, None)

    # Remove from database (scoped to tenant)
    from sqlalchemy import delete as sql_delete
    from app.models.database import Message, Memory
    try:
        async with async_session() as session:
            await session.execute(sql_delete(AgentState).where(
                AgentState.agent_id == agent_id,
                AgentState.tenant_id == ctx.tenant_id,
            ))
            # Clean up messages associated with this agent
            # (Message has no tenant_id; scoped via agent_id which is tenant-specific)
            await session.execute(sql_delete(Message).where(
                Message.agent_id == agent_id,
            ))
            # Clean up memories (session-based, scoped to tenant)
            await session.execute(sql_delete(Memory).where(
                Memory.session_id.like(f"%{agent_id}%"),
                Memory.tenant_id == ctx.tenant_id,
            ))
            await session.commit()
    except Exception as e:
        logger.error("Failed to delete agent '%s' from DB: %s", agent_id, e)
        raise HTTPException(status_code=500, detail=f"Database deletion failed: {e}")

    # Clean up agent workspace directory (tenant-scoped)
    import shutil
    from pathlib import Path
    workspaces_dir = Path(__file__).parent.parent.parent / "workspaces"
    agent_workspace = workspaces_dir / ctx.tenant_id / agent_id
    if agent_workspace.exists():
        try:
            shutil.rmtree(agent_workspace)
            logger.info("Agent workspace deleted: %s", agent_workspace)
        except Exception as e:
            logger.warning("Failed to delete agent workspace %s: %s", agent_workspace, e)

    logger.info("Agent deleted: %s (tenant=%s)", agent_id, ctx.tenant_id)
    return {"status": "deleted"}
