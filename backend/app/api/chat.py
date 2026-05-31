import json
import uuid
import base64
import logging
import os
import tempfile
from fastapi import APIRouter, WebSocket, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from app.models.schemas import ChatRequest, StreamChunk
from app.models.database import async_session, Message as MessageModel
from app.core.agent import agent_manager
from app.core.memory import MemoryManager
from app.websocket.handler import ws_manager

logger = logging.getLogger("kevin_agent.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Upload directory
UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "kevin_agent_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class SessionCreateRequest(BaseModel):
    title: str = "New Chat"
    provider: str = ""
    model: str = ""


class ChatWithAttachmentsRequest(BaseModel):
    message: str
    session_id: str
    model: str = ""
    provider: str = ""
    attachments: list[dict] = []  # [{type, name, content, mime_type}]


@router.post("")
async def chat(request: ChatRequest):
    """Send a message and get a streaming response."""
    target_agent_id = request.agent_id or "main"
    logger.info("Chat request: session=%s agent=%s provider=%s model=%s msg_len=%d",
                request.session_id[:8] if request.session_id else "new",
                target_agent_id, request.provider, request.model, len(request.message))
    agent = agent_manager.get_agent(target_agent_id)
    if not agent:
        # Auto-create agent from database or with defaults
        if target_agent_id == "main":
            agent = await agent_manager.create_agent(
                agent_id="main",
                provider=request.provider,
                model=request.model,
                session_id=request.session_id,
            )
        else:
            from app.models.database import AgentState, async_session
            from sqlalchemy import select
            async with async_session() as session:
                result = await session.execute(
                    select(AgentState).where(AgentState.agent_id == target_agent_id)
                )
                state = result.scalar_one_or_none()
            if state:
                agent = await agent_manager.create_agent(
                    agent_id=state.agent_id,
                    provider=state.provider,
                    model=state.model,
                    session_id=request.session_id,
                )
            else:
                raise HTTPException(status_code=404, detail=f"Agent '{target_agent_id}' not found")
    else:
        # Determine effective provider/model: use request values if provided, else keep current
        from app.llm.registry import get_provider
        effective_provider = request.provider or agent.provider_name
        effective_model = request.model or agent.model
        if agent.provider_name != effective_provider or agent.model != effective_model:
            logger.info("Agent model updated: %s/%s -> %s/%s",
                        agent.provider_name, agent.model, effective_provider, effective_model)
            agent.provider_name = effective_provider
            agent.model = effective_model
            # Sync to DB so workflow/list_agents reflect the change
            try:
                from app.models.database import AgentState, async_session
                from sqlalchemy import update as sql_update
                async with async_session() as db_session:
                    await db_session.execute(
                        sql_update(AgentState).where(AgentState.agent_id == target_agent_id).values(
                            provider=effective_provider, model=effective_model
                        )
                    )
                    await db_session.commit()
            except Exception as e:
                logger.warning("Failed to sync agent config to DB: %s", e)
        # Always rebuild LLM provider to pick up latest API key from cfg.providers_config
        agent.llm = get_provider(effective_provider, effective_model)

    async def event_stream():
        try:
            async for chunk in agent.chat(request.message):
                data = chunk.model_dump()
                yield f"data: {json.dumps(data)}\n\n"
        except Exception as e:
            logger.error("Stream error: %s", e)
            error_chunk = StreamChunk(type="error", content=f"Stream error: {str(e)}", agent_id=target_agent_id)
            yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/upload")
async def chat_with_upload(
    message: str = Form(""),
    session_id: str = Form(""),
    provider: str = Form(""),
    model: str = Form(""),
    agent_id: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    """Send a message with file attachments and get a streaming response."""
    target_agent_id = agent_id or "main"
    logger.info("Chat upload: session=%s agent=%s files=%d", session_id[:8] if session_id else "new", target_agent_id, len(files))

    # Process attachments
    attachments = []
    for f in files:
        content_bytes = await f.read()
        mime_type = f.content_type or "application/octet-stream"
        att_name = f.filename or "unknown"

        if mime_type.startswith("image/"):
            # Base64 encode images
            b64 = base64.b64encode(content_bytes).decode("utf-8")
            attachments.append({
                "type": "image",
                "name": att_name,
                "content": f"data:{mime_type};base64,{b64}",
                "mime_type": mime_type,
            })
        elif mime_type.startswith("audio/"):
            # Save audio to temp file, provide path
            att_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{att_name}")
            with open(att_path, "wb") as fp:
                fp.write(content_bytes)
            attachments.append({
                "type": "audio",
                "name": att_name,
                "content": att_path,
                "mime_type": mime_type,
            })
        else:
            # Text files: try to decode as text
            try:
                text_content = content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text_content = content_bytes.decode("gbk")
                except UnicodeDecodeError:
                    text_content = base64.b64encode(content_bytes).decode("utf-8")
                    text_content = f"[Binary file, base64 encoded]\n{text_content[:500]}"
            attachments.append({
                "type": "file",
                "name": att_name,
                "content": text_content[:50000],  # Limit text content
                "mime_type": mime_type,
            })

    # Get or create agent
    agent = agent_manager.get_agent(target_agent_id)
    if not agent:
        if target_agent_id == "main":
            agent = await agent_manager.create_agent(
                agent_id="main",
                provider=provider,
                model=model,
                session_id=session_id,
            )
        else:
            from app.models.database import AgentState, async_session
            from sqlalchemy import select
            async with async_session() as session:
                result = await session.execute(
                    select(AgentState).where(AgentState.agent_id == target_agent_id)
                )
                state = result.scalar_one_or_none()
            if state:
                agent = await agent_manager.create_agent(
                    agent_id=state.agent_id,
                    provider=state.provider,
                    model=state.model,
                    session_id=session_id,
                )
            else:
                raise HTTPException(status_code=404, detail=f"Agent '{target_agent_id}' not found")
    else:
        from app.llm.registry import get_provider
        effective_provider = provider or agent.provider_name
        effective_model = model or agent.model
        if agent.provider_name != effective_provider or agent.model != effective_model:
            agent.provider_name = effective_provider
            agent.model = effective_model
            agent.llm = get_provider(effective_provider, effective_model)
            # Sync to DB so workflow/list_agents reflect the change
            try:
                from app.models.database import AgentState, async_session
                from sqlalchemy import update as sql_update
                async with async_session() as db_session:
                    await db_session.execute(
                        sql_update(AgentState).where(AgentState.agent_id == target_agent_id).values(
                            provider=effective_provider, model=effective_model
                        )
                    )
                    await db_session.commit()
            except Exception as e:
                logger.warning("Failed to sync agent config to DB: %s", e)

    async def event_stream():
        try:
            async for chunk in agent.chat(message, attachments=attachments):
                data = chunk.model_dump()
                yield f"data: {json.dumps(data)}\n\n"
        except Exception as e:
            logger.error("Stream error: %s", e)
            error_chunk = StreamChunk(type="error", content=f"Stream error: {str(e)}", agent_id=target_agent_id)
            error_chunk = StreamChunk(type="error", content=f"Stream error: {str(e)}", agent_id="main")
            yield f"data: {json.dumps(error_chunk.model_dump())}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe an audio file to text using the configured LLM provider.

    For providers that support audio transcription (e.g. OpenAI Whisper).
    Falls back to a simple placeholder if not available.
    """
    content_bytes = await file.read()
    mime_type = file.content_type or "audio/wav"
    filename = file.filename or "audio.wav"

    logger.info("Transcribe request: file=%s size=%d", filename, len(content_bytes))

    # Save to temp file
    att_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex[:8]}_{filename}")
    with open(att_path, "wb") as fp:
        fp.write(content_bytes)

    try:
        # Try OpenAI Whisper API
        from app.config import default_provider, default_model
        from app.llm.registry import get_provider

        provider_name = default_provider
        llm = get_provider(provider_name, default_model)

        if hasattr(llm, 'transcribe'):
            text = await llm.transcribe(att_path)
            return {"text": text, "success": True}

        # Fallback: try openai client directly
        try:
            from openai import AsyncOpenAI
            from app.config import app_config
            api_key = getattr(app_config, '_api_keys', {}).get('openai', '')
            if api_key:
                client = AsyncOpenAI(api_key=api_key)
                with open(att_path, "rb") as audio_file:
                    transcript = await client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                    )
                return {"text": transcript.text, "success": True}
        except Exception as e:
            logger.warning("Whisper transcription failed: %s", e)

        return {"text": "", "success": False, "error": "Audio transcription not available for this provider"}
    finally:
        # Clean up temp file
        try:
            os.unlink(att_path)
        except Exception:
            pass


@router.post("/sessions")
async def create_session(request: SessionCreateRequest = None):
    """Create a new chat session."""
    req = request or SessionCreateRequest()
    session_id = str(uuid.uuid4())
    memory = MemoryManager(session_id)
    await memory.create_or_update_conversation(
        title=req.title,
        model=req.model,
        provider=req.provider,
    )
    logger.info("Session created: %s", session_id[:8])
    return {"session_id": session_id, "title": req.title}


@router.get("/sessions")
async def list_sessions():
    """List all chat sessions."""
    memory = MemoryManager("")
    conversations = await memory.get_conversations()
    # Strip unnecessary data to reduce response size
    slim_sessions = [
        {
            "session_id": c["session_id"],
            "title": c["title"][:80] if c["title"] else "New Chat",
            "model": c["model"],
            "provider": c["provider"],
            "created_at": c.get("created_at", ""),
            "updated_at": c["updated_at"],
        }
        for c in conversations
    ]
    return {"sessions": slim_sessions}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, limit: int = 100, include_children: bool = True):
    """Get messages for a specific session, optionally including child agent messages."""
    from sqlalchemy import select, or_

    async with async_session() as session:
        if include_children:
            # Get messages from parent session AND all child sessions
            # Child sessions are named: child_{agent_id}_{parent_prefix}_{uuid}
            # where parent_prefix is the first 8 chars of parent session_id
            parent_prefix = session_id[:8]
            stmt = (
                select(MessageModel)
                .where(
                    or_(
                        MessageModel.session_id == session_id,
                        MessageModel.session_id.like(f"child_%_{parent_prefix}_%"),
                    )
                )
                .order_by(MessageModel.id)
                .limit(limit)
            )
        else:
            stmt = (
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.id)
                .limit(limit)
            )

        result = await session.execute(stmt)
        messages = []
        for msg in result.scalars():
            messages.append({
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "tool_calls": json.loads(msg.tool_calls) if msg.tool_calls else None,
                "tool_call_id": msg.tool_call_id or "",
                "agent_id": msg.agent_id or "main",
                "session_id": msg.session_id,
                "created_at": msg.created_at.isoformat() if msg.created_at else "",
            })

    return {"messages": messages, "session_id": session_id}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session and its messages."""
    memory = MemoryManager(session_id)
    deleted = await memory.delete_conversation(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time agent updates."""
    await ws_manager.handle_connection(websocket)
