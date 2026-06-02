import json
import asyncio
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from app.core.agent import agent_manager

logger = logging.getLogger("kevin_agent.websocket")


class ConnectionManager:
    """Manages WebSocket connections for real-time agent collaboration visualization.

    Supports tenant-scoped connections: each connection is associated with a tenant_id,
    and broadcasts only go to connections within the same tenant.
    """

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._connection_tenant: dict[WebSocket, str] = {}  # websocket -> tenant_id
        self._agent_update_queue: asyncio.Queue = asyncio.Queue()

    async def connect(self, websocket: WebSocket, tenant_id: str = "default"):
        await websocket.accept()
        self.active_connections.add(websocket)
        self._connection_tenant[websocket] = tenant_id
        logger.info("WebSocket connected (tenant=%s), total=%d", tenant_id, len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        self._connection_tenant.pop(websocket, None)
        logger.info("WebSocket disconnected, total=%d", len(self.active_connections))

    async def broadcast(self, message: dict, tenant_id: str = None):
        """Broadcast a message to connected clients. If tenant_id is set, only to that tenant."""
        dead = set()
        for connection in self.active_connections:
            if tenant_id and self._connection_tenant.get(connection) != tenant_id:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                dead.add(connection)
        if dead:
            self.active_connections -= dead
            for c in dead:
                self._connection_tenant.pop(c, None)

    async def send_agent_update(self, agent_id: str, status: str, tenant_id: str = None, extra_data: dict = None):
        """Send agent status update to clients with full agent state.

        Also handles special lifecycle events:
        - agent_id == "__agent_created__": broadcast new agent info
        - agent_id == "__agent_deleted__": broadcast agent deletion
        """
        # Handle agent_created event
        if agent_id == "__agent_created__" and extra_data:
            await self.broadcast({
                "type": "agent_created",
                "agent": extra_data,
            }, tenant_id=tenant_id)
            return

        # Handle agent_deleted event
        if agent_id == "__agent_deleted__" and extra_data:
            await self.broadcast({
                "type": "agent_deleted",
                "agent_id": extra_data.get("agent_id", ""),
            }, tenant_id=tenant_id)
            return

        # Normal agent status update
        message = {
            "type": "agent_update",
            "agent_id": agent_id,
            "status": status,
        }
        # Enrich with current agent state from in-memory or DB
        agent = agent_manager.get_agent(agent_id, tenant_id=tenant_id)
        if agent:
            message["model"] = agent.model
            message["provider"] = agent.provider_name
            message["current_task"] = agent.current_task
        await self.broadcast(message, tenant_id=tenant_id)

    async def send_stream_chunk(self, chunk: dict, tenant_id: str = None):
        """Send a streaming chunk to clients."""
        await self.broadcast({
            "type": "stream",
            **chunk,
        }, tenant_id=tenant_id)

    async def handle_connection(self, websocket: WebSocket, tenant_id: str = "default"):
        """Handle a WebSocket connection lifecycle."""
        await self.connect(websocket, tenant_id=tenant_id)
        try:
            # Send initial state (scoped to tenant)
            states = await agent_manager.get_all_agent_states(tenant_id=tenant_id)
            await websocket.send_json({
                "type": "init",
                "agents": states,
            })

            # Listen for messages
            while True:
                data = await websocket.receive_json()
                await self._handle_message(websocket, data, tenant_id=tenant_id)
        except WebSocketDisconnect:
            self.disconnect(websocket)
        except Exception as e:
            logger.warning("WebSocket error: %s", e)
            self.disconnect(websocket)

    async def _handle_message(self, websocket: WebSocket, data: dict, tenant_id: str = "default"):
        """Handle incoming WebSocket messages."""
        msg_type = data.get("type")

        if msg_type == "ping":
            await websocket.send_json({"type": "pong"})

        elif msg_type == "get_agents":
            states = await agent_manager.get_all_agent_states(tenant_id=tenant_id)
            await websocket.send_json({"type": "agents", "agents": states})


ws_manager = ConnectionManager()
