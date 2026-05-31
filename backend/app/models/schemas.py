from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# Chat schemas
class ChatRequest(BaseModel):
    message: str
    session_id: str
    model: str = ""
    provider: str = ""
    agent_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    agent_id: str = "main"
    tool_calls: list = []


class StreamChunk(BaseModel):
    type: str  # text, tool_call, tool_result, status, agent_update, done, error
    content: str = ""
    agent_id: str = "main"
    metadata: dict = {}


# Agent schemas
class AgentCreate(BaseModel):
    name: str
    model: str = ""
    provider: str = ""
    parent_agent_id: Optional[str] = None
    task: Optional[str] = None


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    status: str
    model: str
    provider: str
    current_task: Optional[str] = None
    parent_agent_id: Optional[str] = None
    created_at: datetime


class AgentNode(BaseModel):
    id: str
    name: str
    status: str
    model: str
    current_task: Optional[str] = None
    position: dict = {"x": 0, "y": 0}
    provider: str = ""
    parent_agent_id: Optional[str] = None


class AgentEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str = ""
    animated: bool = True


# Skill schemas
class SkillCreate(BaseModel):
    name: str
    description: str
    instruction: str


class SkillResponse(BaseModel):
    id: int
    name: str
    description: str
    instruction: str
    success_count: int
    fail_count: int
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SkillUpdate(BaseModel):
    description: Optional[str] = None
    instruction: Optional[str] = None
    is_active: Optional[bool] = None


# Model config schemas
class ModelConfig(BaseModel):
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class ProviderInfo(BaseModel):
    name: str
    models: list[str]
    is_configured: bool


# Workflow visualization
class WorkflowSnapshot(BaseModel):
    agents: list[AgentNode]
    edges: list[AgentEdge]
    active_conversations: list[str] = []
