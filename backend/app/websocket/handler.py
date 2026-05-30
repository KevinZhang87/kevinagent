import json
import asyncio
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from app.core.agent import agent_manager

logger = logging.getLogger("kevin_agent.websocket")


class ConnectionManager:
    """Manages WebSocket connections for real-time agent collaboration visualization."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._agent_update_queue: asyncio.Queue = asyncio.Queue()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WebSocket connected, total=%d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info("WebSocket disconnected, total=%d", len(self.active_connections))

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        dead = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.add(connection)
        if dead:
            self.active_connections -= dead

    async def send_agent_update(self, agent_id: str, status: str):
        """Send agent status update to all clients with full agent state."""
        message = {
            "type": "agent_update",
            "agent_id": agent_id,
            "status": status,
        }
        # Enrich with current agent state from in-memory or DB
        agent = agent_manager.get_agent(agent_id)
        if agent:
            message["model"] = agent.model
            message["provider"] = agent.provider_name
            message["current_task"] = agent.current_task
        await self.broadcast(message)

    async def send_stream_chunk(self, chunk: dict):
        """Send a streaming chunk to all clients."""
        await self.broadcast({
            "type": "stream",
            **chunk,
        })

    async def handle_connection(self, websocket: WebSocket):
        """Handle a WebSocket connection lifecycle."""
        await self.connect(websocket)
        try:
            # Send initial state
            states = await agent_manager.get_all_agent_states()
            await websocket.send_json({
                "type": "init",
                "agents": states,
            })

            # Listen for messages
            while True:
                data = await websocket.receive_json()
                await self._handle_message(websocket, data)
        except WebSocketDisconnect:
            self.disconnect(websocket)
        except Exception as e:
            logger.warning("WebSocket error: %s", e)
            self.disconnect(websocket)

    async def _handle_message(self, websocket: WebSocket, data: dict):
        """Handle incoming WebSocket messages."""
        msg_type = data.get("type")

        if msg_type == "ping":
            await websocket.send_json({"type": "pong"})

        elif msg_type == "get_agents":
            states = await agent_manager.get_all_agent_states()
            await websocket.send_json({"type": "agents", "agents": states})


ws_manager = ConnectionManager()
