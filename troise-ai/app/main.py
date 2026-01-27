"""TROISE AI - FastAPI Application Entry Point.

Provides WebSocket-based chat interface with:
- Plugin auto-discovery at startup
- LLM-based routing to skills/agents
- Preprocessing pipeline (prompt sanitization, file analysis)
- Postprocessing pipeline (artifact extraction)
- Streaming responses
- User question handling for agents
- Cancellation support
- DynamoDB session persistence
"""
import sys
sys.path.insert(0, '/shared')

# Suppress harmless OpenTelemetry context detachment errors from Strands SDK
# These occur when async context tokens cross boundaries but don't affect functionality
import logging
_otel_context_logger = logging.getLogger("opentelemetry.context")
_otel_context_logger.setLevel(logging.CRITICAL)

import asyncio
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware

from datetime import datetime, timezone

from app.core import (
    Config,
    Container,
    create_container,
    ExecutionContext,
    PluginRegistry,
    Router,
    Executor,
)
from app.core.router import RoutingResult
from app.core.context import Message, UserProfile, UserConfig
from app.core.interfaces.services import IVRAMOrchestrator
from app.core.interfaces.storage import IFileStorage
from app.core.interfaces.queue import QueuedRequest, UserTier
from app.services import QueueManager, CircuitBreakerRegistry, VisibilityMonitor
from app.adapters.websocket.factory import get_message_builder

# Preprocessing imports
from app.preprocessing import (
    PromptSanitizer,
    FileExtractionRouter,
    OutputArtifactDetector,
)

# Postprocessing imports
from app.postprocessing import ArtifactExtractionChain
from app.adapters.formatters import DiscordResponseFormatter, WebResponseFormatter, CLIResponseFormatter
from app.services.response_handler import ResponseHandler

# Session persistence
from app.adapters.dynamodb.main_adapter import TroiseMainAdapter

# File storage
from app.adapters.minio import MinIOAdapter

# Configure logging via shared logging service
import logging_client
logger = logging_client.setup_logger('troise-ai')

# Global container and services
container: Optional[Container] = None
registry: Optional[PluginRegistry] = None
router: Optional[Router] = None
executor: Optional[Executor] = None
queue_manager: Optional[QueueManager] = None
visibility_monitor: Optional[VisibilityMonitor] = None
circuit_registry: Optional[CircuitBreakerRegistry] = None


# ==============================================================================
# Non-Blocking Persistence Helpers
# ==============================================================================

async def _persist_message_safe(
    adapter: TroiseMainAdapter,
    session_id: str,
    role: str,
    content: str,
    **kwargs,
) -> None:
    """Persist message with error logging (non-blocking fire-and-forget)."""
    try:
        await adapter.add_message(
            session_id=session_id,
            role=role,
            content=content,
            **kwargs,
        )
    except Exception as e:
        logger.warning(f"Failed to persist {role} message: {e}")


async def _persist_assistant_message_safe(
    adapter: TroiseMainAdapter,
    session_id: str,
    session: Optional[Any],
    result: Any,
    agent_name: str,
) -> None:
    """Persist assistant message and update session (non-blocking fire-and-forget)."""
    try:
        await adapter.add_message(
            session_id=session_id,
            role="assistant",
            content=result.content,
            tool_calls=result.tool_calls if hasattr(result, 'tool_calls') else None,
            metadata={
                "source_type": getattr(result, 'source_type', None),
                "source_name": getattr(result, 'source_name', None),
            },
        )

        if session:
            await adapter.update_session(
                session,
                agent_name=agent_name,
                increment_messages=True,
            )
    except Exception as e:
        logger.warning(f"Failed to persist assistant message: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    global container, registry, router, executor, queue_manager
    global visibility_monitor, circuit_registry

    logger.info("Starting TROISE AI...")

    # Create container and resolve services
    container = create_container()
    config = container.resolve(Config)
    registry = container.resolve(PluginRegistry)

    # Discover plugins
    plugin_dirs = [Path("app/plugins")]
    await registry.discover(plugin_dirs)
    logger.info(
        f"Discovered: {registry.skill_count} skills, "
        f"{registry.agent_count} agents, {registry.tool_count} tools"
    )

    # Load graph definitions
    from app.graphs import load_graphs
    from app.core.graph import GraphRegistry
    graph_registry = container.resolve(GraphRegistry)
    graphs_loaded = load_graphs(graph_registry, container)
    logger.info(f"Loaded {graphs_loaded} graph definitions")

    # Resolve router and executor from container (already registered)
    router = container.resolve(Router)
    executor = container.resolve(Executor)

    # Resolve circuit breaker registry
    circuit_registry = container.resolve(CircuitBreakerRegistry)
    logger.info("Circuit breaker registry initialized")

    # Start queue manager (with circuit breaker)
    queue_manager = container.resolve(QueueManager)
    await queue_manager.start()
    logger.info(f"Queue manager started with {config.queue.worker_count} workers")

    # Start visibility monitor (stuck request detection)
    visibility_monitor = container.resolve(VisibilityMonitor)
    await visibility_monitor.start()
    logger.info("Visibility monitor started")

    # Initialize MinIO adapter (create bucket and lifecycle policy)
    try:
        file_storage: MinIOAdapter = container.resolve(MinIOAdapter)
        await file_storage.initialize()
        logger.info("MinIO file storage initialized")
    except Exception as e:
        logger.warning(f"MinIO initialization failed (non-fatal): {e}")

    logger.info("TROISE AI ready")

    yield

    # Shutdown
    logger.info("Shutting down TROISE AI...")

    # Stop visibility monitor first
    if visibility_monitor:
        await visibility_monitor.stop()
        logger.info("Visibility monitor stopped")

    # Stop queue manager (graceful worker shutdown)
    if queue_manager:
        await queue_manager.stop()
        logger.info("Queue manager stopped")


# Create FastAPI app
app = FastAPI(
    title="TROISE AI",
    description="Personal AI Assistant with Skills and Agents",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    queue_status = None
    if queue_manager:
        queue_status = {
            "running": queue_manager.is_running,
            "queue_depth": queue_manager.get_queue_depth(),
            "in_flight": queue_manager.get_in_flight_count(),
        }

    return {
        "status": "healthy",
        "skills": registry.skill_count if registry else 0,
        "agents": registry.agent_count if registry else 0,
        "tools": registry.tool_count if registry else 0,
        "queue": queue_status,
    }


@app.get("/plugins")
async def list_plugins():
    """List all registered plugins."""
    if not registry:
        return {"error": "Registry not initialized"}

    return {
        "skills": registry.list_skills(),
        "agents": registry.list_agents(),
        "tools": registry.list_tools(),
    }


@app.get("/routing-table")
async def get_routing_table():
    """Get the current routing table for debugging."""
    if not router:
        return {"error": "Router not initialized"}

    return {
        "routing_table": router.get_routing_table()
    }


@app.get("/models")
async def list_models():
    """List available models from configured backends.

    Returns list of models available from Ollama/SGLang backends
    for TUI model selection.

    Returns:
        List of model info including name, size, parameters.
    """
    if not container:
        return {"error": "Service not initialized"}

    try:
        orchestrator: IVRAMOrchestrator = container.resolve(IVRAMOrchestrator)

        # Get models from orchestrator (which queries backends)
        models = await orchestrator.list_available_models()

        return {
            "models": models,
            "count": len(models),
        }
    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        return {
            "models": [],
            "count": 0,
            "error": str(e),
        }


@app.get("/models/{model_name}")
async def get_model_info(model_name: str):
    """Get detailed info about a specific model.

    Args:
        model_name: Name of the model to get info for.

    Returns:
        Model details including parameters, context length, etc.
    """
    if not container:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        orchestrator: IVRAMOrchestrator = container.resolve(IVRAMOrchestrator)

        # Get model info from orchestrator
        model_info = await orchestrator.get_model_info(model_name)

        if not model_info:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_name}")

        return model_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model info: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/files/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    session_id: str = Form(...),
):
    """Upload files to MinIO storage and extract content.

    Args:
        files: List of files to upload.
        session_id: Session ID for namespacing uploads.

    Returns:
        List of file references with IDs and extracted content.
    """
    if not container:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        file_storage: IFileStorage = container.resolve(IFileStorage)
        extraction_router = container.resolve(FileExtractionRouter)

        uploaded_files = []

        for upload in files:
            # Generate unique UUID for this file
            uuid_part = str(uuid.uuid4())

            # Read file content
            content_bytes = await upload.read()
            mimetype = upload.content_type or "application/octet-stream"

            # Upload to MinIO - returns composite file_id "{session_id}:{uuid}"
            file_id = await file_storage.upload(
                file_id=uuid_part,
                content=content_bytes,
                mimetype=mimetype,
                session_id=session_id,
            )

            # Store temporarily for extraction
            temp_path = Path(f"/tmp/troise-uploads/{session_id}")
            temp_path.mkdir(parents=True, exist_ok=True)
            temp_file = temp_path / f"{uuid_part}_{upload.filename}"
            temp_file.write_bytes(content_bytes)

            # Extract content using extraction router
            file_store = {}
            file_refs = await extraction_router.process_files(
                [{"path": str(temp_file), "mimetype": mimetype}],
                file_store,
            )

            # Get extracted content
            extracted_content = None
            if file_refs:
                ref = file_refs[0]
                stored_data = file_store.get(ref.file_id, {})
                extracted_content = stored_data.get("content", "")

            # Cleanup temp file
            temp_file.unlink(missing_ok=True)

            uploaded_files.append({
                "file_id": file_id,  # Composite: "{session_id}:{uuid}"
                "filename": upload.filename,
                "mimetype": mimetype,
                "size": len(content_bytes),
                "extracted_content": extracted_content,
            })

            logger.info(f"Uploaded file {file_id}: {upload.filename} ({len(content_bytes)} bytes)")

        return {
            "session_id": session_id,
            "files": uploaded_files,
            "count": len(uploaded_files),
        }

    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queue/status")
async def queue_status():
    """Get queue health and status metrics.

    Returns:
        Queue depth, in-flight count, worker status, metrics, and circuit breaker state.
    """
    if not queue_manager:
        return {"error": "Queue manager not initialized"}

    status = queue_manager.get_status()

    # Add circuit breaker metrics
    if circuit_registry:
        status["circuit_breakers"] = {
            name: {
                "state": metrics.state.value,
                "failure_rate": round(metrics.failure_rate, 3),
                "consecutive_failures": metrics.consecutive_failures,
                "consecutive_successes": metrics.consecutive_successes,
                "total_failures": metrics.total_failures,
                "total_successes": metrics.total_successes,
                "open_count": metrics.open_count,
            }
            for name, metrics in circuit_registry.get_all_metrics().items()
        }

    return status


@app.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    session_id: Optional[str] = Query(default=None, description="Existing session ID for reconnection"),
    user_id: Optional[str] = Query(default=None, description="User ID"),
    interface: Optional[str] = Query(default="web", description="Interface type: web, discord"),
    token: Optional[str] = Query(default=None, description="Authentication token (JWT for web, HMAC for discord)"),
):
    """
    WebSocket endpoint for chat with preprocessing/postprocessing pipeline.

    Query Parameters:
        session_id: Optional existing session ID for reconnection
        user_id: User identifier (defaults to 'default')
        interface: Interface type - 'web' or 'discord' (defaults to 'web')
        token: Authentication token (JWT for web, HMAC signature for discord)

    Pipeline:
    1. PREPROCESSING
       - PromptSanitizer: Extract clean intent
       - OutputArtifactDetector: Check if user wants file output
       - FileExtractionRouter: Extract file content
       - FileAnalysisAgent: Analyze files with larger model
       - ContextBuilder: Build enriched context

    2. ROUTING
       - Router: Classify and select skill/agent

    3. EXECUTION
       - Executor: Run skill/agent with tools

    4. POSTPROCESSING
       - ArtifactExtractionChain: Extract file artifacts
       - ResponseHandler: Format and send response

    Message format (incoming):
    {
        "type": "message" | "answer" | "cancel" | "history",
        "content": "...",
        "files": [{"path": "...", "mimetype": "..."}],  # Optional
        "request_id": "..." (for answers)
    }

    Message format (outgoing):
    {
        "type": "session_start" | "routing" | "queued" | "response" | "question" | "stream" | "error" | "file" | "history" | "cancelled",
        "session_id": "...",
        "content": "...",
        "request_id": "..." (for questions/queued/cancelled),
        "position": N (for queued - queue position),
        "metadata": {...}
    }
    """
    # Authentication check before accepting connection
    from app.core.auth import get_auth_strategy, is_auth_required

    if is_auth_required(interface or "web"):
        strategy = get_auth_strategy(interface or "web")
        auth_result = await strategy.authenticate(
            token=token,
            interface=interface or "web",
            user_id=user_id,
            bot_id=user_id if interface == "discord" else None,
        )

        if not auth_result.authenticated:
            await websocket.close(code=4001, reason=auth_result.error or "Authentication failed")
            logger.warning(f"WS auth failed for {interface}: {auth_result.error}")
            return

        # Use authenticated user_id if available
        if auth_result.user_id:
            user_id = auth_result.user_id
        logger.info(f"WS authenticated: user={user_id}, interface={interface}")

    await websocket.accept()

    # Default user_id if not provided
    if not user_id:
        user_id = "default"

    # Get session adapter for persistence
    session_adapter: TroiseMainAdapter = container.resolve(TroiseMainAdapter)
    config: Config = container.resolve(Config)

    # Load or create session
    session = None
    conversation_history: List[Message] = []
    is_resumed = False

    try:
        if session_id:
            # Try to load existing session
            session = await session_adapter.get_session(user_id, session_id)
            if session:
                is_resumed = True
                # Load conversation history
                messages = await session_adapter.get_messages(
                    session_id, limit=config.session.max_history_messages
                )
                conversation_history = [
                    Message(role=m.role, content=m.content, timestamp=m.timestamp)
                    for m in messages
                ]
                logger.info(f"Resumed session {session_id} with {len(conversation_history)} messages")

        if not session:
            # Create new session
            session = await session_adapter.create_session(
                user_id=user_id,
                interface=interface,
            )
            session_id = session.session_id
            logger.info(f"Created new session {session_id}")

    except Exception as e:
        logger.error(f"Session persistence error: {e}", exc_info=True)
        # Fall back to in-memory session
        session_id = session_id or str(uuid.uuid4())
        logger.warning(f"Using in-memory session: {session_id}")

    # Create context for this session with session-scoped file store
    context = ExecutionContext(
        user_id=user_id,
        session_id=session_id,
        interface=interface,
        websocket=websocket,
        file_store={},  # Session-scoped file storage
        conversation_history=conversation_history,
    )

    # Track processed message IDs for idempotency
    processed_message_ids: Set[str] = set()

    # Resolve preprocessing services
    prompt_sanitizer = container.resolve(PromptSanitizer)
    extraction_router = container.resolve(FileExtractionRouter)
    artifact_detector = container.resolve(OutputArtifactDetector)
    artifact_chain = container.resolve(ArtifactExtractionChain)

    # Get formatter based on interface
    if interface == "discord":
        formatter = container.resolve(DiscordResponseFormatter)
    elif interface == "cli":
        formatter = container.resolve(CLIResponseFormatter)
    else:
        formatter = container.resolve(WebResponseFormatter)

    # Send session info to client
    await websocket.send_json({
        "type": "session_start",
        "session_id": session_id,
        "user_id": user_id,
        "interface": interface,
        "resumed": is_resumed,
        "message_count": len(conversation_history),
    })

    logger.info(f"WebSocket session started: {session_id} (resumed={is_resumed})")

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "ping":
                # Heartbeat from Discord bot
                await websocket.send_json({"type": "pong"})
                continue

            elif msg_type == "history":
                # Client requesting conversation history
                try:
                    history_messages = [
                        {
                            "role": msg.role,
                            "content": msg.content,
                            "timestamp": msg.timestamp,
                        }
                        for msg in context.conversation_history
                    ]
                    await websocket.send_json({
                        "type": "history",
                        "session_id": session_id,
                        "messages": history_messages,
                    })
                except Exception as e:
                    logger.error(f"Error fetching history: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Failed to fetch history: {str(e)}",
                    })

            elif msg_type == "message":
                # Process user message
                content = data.get("content", "")
                file_uploads = data.get("files", [])
                message_id = data.get("message_id")  # Optional client-provided ID
                metadata = data.get("metadata", {})  # Discord context from client

                # Extract Discord-specific context from metadata
                if metadata:
                    context.discord_channel_id = metadata.get("channel_id")
                    context.discord_message_channel_id = metadata.get("message_channel_id")
                    context.discord_message_id = metadata.get("message_id")
                    context.discord_guild_id = metadata.get("guild_id")

                # Parse user_config from message (for model/temperature overrides)
                user_config_data = data.get("user_config", {})
                user_config: Optional[UserConfig] = None
                if user_config_data:
                    user_config = UserConfig(
                        model=user_config_data.get("model"),
                        temperature=user_config_data.get("temperature"),
                        thinking_enabled=user_config_data.get("thinking_enabled"),
                        enable_web_search=user_config_data.get("enable_web_search"),
                    )
                    context.user_config = user_config
                    logger.info(f"User config received: model={user_config.model}, temp={user_config.temperature}")

                # Idempotency check - skip duplicate messages
                if message_id:
                    if message_id in processed_message_ids:
                        logger.debug(f"Skipping duplicate message: {message_id}")
                        continue
                    processed_message_ids.add(message_id)

                if not content and not file_uploads:
                    continue

                # If no content but there are file uploads, generate analysis-oriented content
                # This ensures routing treats file-only uploads as analysis requests, not generation
                if not content and file_uploads:
                    file_names = [f.get("filename", "file") for f in file_uploads]
                    content = f"Analyze this file: {', '.join(file_names)}"

                try:
                    # ==========================================================
                    # RESET REQUEST-SCOPED STATE
                    # ==========================================================
                    # Clear generated_images from previous request to prevent duplicates
                    context.generated_images.clear()

                    # ==========================================================
                    # FILE EXTRACTION (before message persistence)
                    # ==========================================================
                    file_refs = []
                    file_context = None
                    system_context = ""

                    if file_uploads:
                        # Determine file upload format
                        first_file = file_uploads[0]
                        temp_dir = Path(f"/tmp/troise-ws/{session_id}")
                        temp_dir.mkdir(parents=True, exist_ok=True)

                        if first_file.get("file_id"):
                            # MinIO-based file uploads: download from storage
                            file_storage: IFileStorage = container.resolve(IFileStorage)

                            for file_ref in file_uploads:
                                file_id = file_ref.get("file_id")
                                mimetype = file_ref.get("mimetype", "application/octet-stream")

                                try:
                                    # Download from MinIO
                                    content_bytes = await file_storage.download(file_id)

                                    # Save to temp for extraction
                                    temp_file = temp_dir / file_id
                                    temp_file.write_bytes(content_bytes)

                                    # Process through extraction router
                                    refs = await extraction_router.process_files(
                                        [{"path": str(temp_file), "mimetype": mimetype}],
                                        context.file_store,
                                    )
                                    file_refs.extend(refs)

                                    # Cleanup temp file
                                    temp_file.unlink(missing_ok=True)

                                except FileNotFoundError:
                                    logger.warning(f"File not found in storage: {file_id}")
                                except Exception as e:
                                    logger.error(f"Failed to download file {file_id}: {e}")

                        elif first_file.get("base64_data"):
                            # Base64-encoded file uploads from Discord
                            import base64 as b64
                            logger.info(f"Processing {len(file_uploads)} base64 file(s)")

                            for file_ref in file_uploads:
                                filename = file_ref.get("filename", "unknown")
                                mimetype = file_ref.get("mimetype", "application/octet-stream")
                                base64_data = file_ref.get("base64_data", "")
                                logger.info(f"File: {filename}, mimetype: {mimetype}, data_len: {len(base64_data)}")

                                try:
                                    # Decode base64 content
                                    content_bytes = b64.b64decode(base64_data)

                                    # Save to temp for extraction
                                    safe_filename = filename.replace("/", "_").replace("\\", "_")
                                    temp_file = temp_dir / safe_filename
                                    temp_file.write_bytes(content_bytes)

                                    # Process through extraction router
                                    refs = await extraction_router.process_files(
                                        [{"path": str(temp_file), "mimetype": mimetype}],
                                        context.file_store,
                                    )
                                    file_refs.extend(refs)

                                    # Cleanup temp file
                                    temp_file.unlink(missing_ok=True)

                                    logger.debug(f"Processed base64 file: {filename} ({len(content_bytes)} bytes)")

                                except Exception as e:
                                    logger.error(f"Failed to process base64 file {filename}: {e}")

                        else:
                            # Legacy path-based file uploads
                            file_refs = await extraction_router.process_files(
                                file_uploads,
                                context.file_store,
                            )

                        logger.debug(f"Extracted {len(file_refs)} files")

                    # Build file context directly from extracted content
                    if file_refs:
                        # Build system_context for skill (full content)
                        context_parts = ["**Attached Files:**\n"]
                        file_summaries = []

                        for ref in file_refs:
                            content = context.file_store.get(ref.file_id, {}).get("content", "")
                            context_parts.append(f"\n### {ref.filename}\n{content}")
                            file_summaries.append(f"{ref.filename}: {content}")

                        system_context = "\n".join(context_parts)
                        file_context = "\n".join(file_summaries)
                        logger.info(f"file_context for router ({len(file_context)} chars): {file_context[:200]}...")

                    # ==========================================================
                    # MESSAGE PERSISTENCE (with extracted file content)
                    # ==========================================================

                    # Build enriched content for persistence (user message + extracted files)
                    enriched_content = content
                    if file_context:
                        enriched_content = f"{content}\n\n[Extracted File Content]\n{file_context}"

                    # Store in context history (with file content for follow-ups)
                    context.conversation_history.append(
                        Message(role="user", content=enriched_content)
                    )
                    context.last_user_message = content  # Original content for processing

                    # Persist enriched user message to DynamoDB (fire-and-forget)
                    asyncio.create_task(
                        _persist_message_safe(session_adapter, session_id, "user", enriched_content)
                    )

                    # ==========================================================
                    # PREPROCESSING PHASE
                    # ==========================================================

                    # Run PromptSanitizer and OutputArtifactDetector in PARALLEL
                    sanitize_task = asyncio.create_task(
                        prompt_sanitizer.sanitize(content)  # Sanitize original content
                    )
                    detect_task = asyncio.create_task(
                        artifact_detector.detect(content)
                    )

                    sanitized, artifact_requested = await asyncio.gather(
                        sanitize_task, detect_task
                    )

                    logger.info(
                        f"Preprocessing: action_type={sanitized.action_type}, "
                        f"artifact_requested={artifact_requested}, "
                        f"expected_filename={sanitized.expected_filename}"
                    )

                    # Include raw content for modify actions
                    if sanitized.action_type == "modify" and file_refs:
                        context.raw_file_contents = {
                            ref.file_id: context.file_store.get(ref.file_id, {}).get("content", "")
                            for ref in file_refs
                        }

                    # Build agent prompt
                    agent_prompt = prompt_sanitizer.build_agent_prompt(
                        sanitized=sanitized,
                        file_context=system_context,
                    )

                    # Store preprocessing results in context
                    context.system_context = system_context
                    context.file_analyses = []  # No longer using FileAnalysis
                    context.clean_intent = sanitized.intent
                    context.action_type = sanitized.action_type
                    context.expected_filename = sanitized.expected_filename

                    # ==========================================================
                    # MODEL VALIDATION (before routing)
                    # ==========================================================

                    if user_config and user_config.model:
                        orchestrator: IVRAMOrchestrator = container.resolve(IVRAMOrchestrator)

                        # Check if model exists in available_models
                        model_caps = orchestrator.get_model_capabilities(user_config.model)

                        if not model_caps:
                            # Model not in profile - return error with available options
                            available_models = await orchestrator.list_available_models()
                            await websocket.send_json({
                                "type": "error",
                                "error": f"Model '{user_config.model}' not available in current profile.",
                                "available_models": available_models,
                            })
                            continue  # Skip this message, wait for next

                        # Capability validation warnings
                        if user_config.thinking_enabled and not model_caps.supports_thinking:
                            await websocket.send_json({
                                "type": "warning",
                                "warning": f"Model '{user_config.model}' does not support extended thinking. Proceeding without thinking.",
                            })
                            user_config.thinking_enabled = False  # Silently disable

                    # ==========================================================
                    # ROUTING PHASE (with interceptor)
                    # ==========================================================

                    # INTERCEPTOR: Check for user model override (bypass LLM classification)
                    if user_config and user_config.model:
                        routing_result = RoutingResult(
                            type="agent",
                            name="general",
                            reason=f"User selected model: {user_config.model}",
                            confidence=1.0,
                            fallback=False,
                        )
                        logger.info(f"Routing intercepted - user model: {user_config.model}")
                    else:
                        # Normal routing - router stays pure (SRP)
                        # Use file_uploads (user sent) not file_refs (extracted) for attachment detection
                        # This ensures correct routing even if extraction fails
                        routing_result = await router.route(
                            sanitized.intent,
                            {"user_id": user_id},
                            file_context=file_context,
                            has_attachments=bool(file_uploads),
                        )

                    # Send routing info
                    await websocket.send_json({
                        "type": "routing",
                        "skill_or_agent": routing_result.name,
                        "routing_type": routing_result.type,
                        "reason": routing_result.reason,
                    })

                    # ==========================================================
                    # EXECUTION PHASE (Via Queue)
                    # ==========================================================

                    # Create queued request
                    request_id = str(uuid.uuid4())

                    # Store request_id in context for streaming state tracking
                    context.request_id = request_id

                    queued_request = QueuedRequest(
                        request_id=request_id,
                        user_id=user_id,
                        session_id=session_id,
                        user_tier=UserTier.NORMAL,  # TODO: Get from user profile
                        routing_result=routing_result,
                        user_input=agent_prompt,
                        context=context,
                        queued_at=datetime.now(timezone.utc),
                    )

                    # Submit to queue
                    await queue_manager.submit(queued_request)

                    # Send queued notification to client
                    position = queue_manager.get_position(request_id)
                    await websocket.send_json({
                        "type": "queued",
                        "request_id": request_id,
                        "position": position,
                    })

                    # Wait for result (timeout based on classification)
                    # IMAGE classification uses image_timeout (900s), others use standard timeouts
                    queue_timeout = config.queue.get_timeout_for_type(
                        routing_result.type, routing_result.classification
                    )
                    try:
                        result = await queue_manager.wait_for_result(
                            request_id,
                            timeout=queue_timeout,
                        )
                    except TimeoutError as e:
                        logger.error(f"Queue timeout for {routing_result.name}: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "content": f"Request timed out after {queue_timeout}s",
                        })
                        continue  # Skip to next message
                    except RuntimeError as e:
                        # Request failed in worker
                        logger.error(f"Queue execution failed: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "content": str(e),
                        })
                        continue

                    # Store response in history
                    context.conversation_history.append(
                        Message(role="assistant", content=result.content)
                    )

                    # Persist assistant message to DynamoDB (fire-and-forget)
                    asyncio.create_task(
                        _persist_assistant_message_safe(
                            session_adapter,
                            session_id,
                            session,
                            result,
                            routing_result.name,
                        )
                    )

                    # ==========================================================
                    # POSTPROCESSING PHASE
                    # ==========================================================

                    # Create response handler and send
                    handler = ResponseHandler(formatter, artifact_chain)

                    # Both agents AND graphs stream content via WebSocket - skip duplicate response message
                    was_streamed = routing_result.type in ("agent", "graph") and context.websocket

                    await handler.send_response(
                        result=result,
                        context=context,
                        artifact_requested=artifact_requested,
                        expected_filename=context.expected_filename,
                        streamed=was_streamed,
                    )

                    # Send completion metrics via interface-specific builder
                    # Builder returns None for interfaces that don't display metrics (e.g., Discord)
                    if context.websocket:
                        builder = get_message_builder(context)
                        metrics_msg = builder.build_completion_metrics(
                            result.metadata or {}, context
                        )
                        if metrics_msg:
                            await websocket.send_json(metrics_msg)

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "content": str(e),
                    })

            elif msg_type == "answer":
                # User answering a question from agent
                request_id = data.get("request_id")
                answer = data.get("content", "")

                if request_id:
                    await context.handle_user_answer(request_id, answer)

            elif msg_type == "command_result":
                # TUI sending back command execution result
                request_id = data.get("request_id")
                stdout = data.get("stdout", "")
                stderr = data.get("stderr", "")
                exit_code = data.get("exit_code", -1)
                status = data.get("status", "completed")

                if request_id:
                    await context.handle_command_result(
                        request_id=request_id,
                        stdout=stdout,
                        stderr=stderr,
                        exit_code=exit_code,
                        status=status,
                    )

            elif msg_type == "cancel":
                # Cancel current operation
                reason = data.get("reason", "User cancelled")
                cancel_request_id = data.get("request_id")

                # Cancel via context (sets cancellation token)
                context.cancel(reason)

                # Also cancel in queue if request_id provided
                if cancel_request_id and queue_manager:
                    await queue_manager.cancel(cancel_request_id)

                await websocket.send_json({
                    "type": "cancelled",
                    "reason": reason,
                    "request_id": cancel_request_id,
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket session ended: {session_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)


# ==============================================================================
# Session Management REST Endpoints
# ==============================================================================

@app.get("/sessions/{user_id}")
async def list_user_sessions(user_id: str, limit: int = 10):
    """List sessions for a user.

    Args:
        user_id: User identifier.
        limit: Maximum number of sessions to return.

    Returns:
        List of session summaries.
    """
    try:
        session_adapter: TroiseMainAdapter = container.resolve(TroiseMainAdapter)
        sessions = await session_adapter.list_sessions(user_id, limit=limit)

        return {
            "user_id": user_id,
            "sessions": [
                {
                    "session_id": s.session_id,
                    "interface": s.interface,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "message_count": s.message_count,
                    "agent_name": s.agent_name,
                    "title": s.title,
                }
                for s in sessions
            ],
            "count": len(sessions),
        }
    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{user_id}/{session_id}")
async def get_session(user_id: str, session_id: str):
    """Get session details.

    Args:
        user_id: User identifier.
        session_id: Session identifier.

    Returns:
        Session details or error.
    """
    try:
        session_adapter: TroiseMainAdapter = container.resolve(TroiseMainAdapter)
        session = await session_adapter.get_session(user_id, session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "interface": session.interface,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "message_count": session.message_count,
            "agent_name": session.agent_name,
            "title": session.title,
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error getting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{user_id}/{session_id}/messages")
async def get_session_messages(
    user_id: str,
    session_id: str,
    limit: int = 50,
    after: Optional[str] = None,
):
    """Get messages for a session.

    Args:
        user_id: User identifier.
        session_id: Session identifier.
        limit: Maximum number of messages to return.
        after: Optional timestamp to paginate after (get messages after this timestamp).

    Returns:
        List of messages.
    """
    try:
        session_adapter: TroiseMainAdapter = container.resolve(TroiseMainAdapter)

        # Verify session belongs to user
        session = await session_adapter.get_session(user_id, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = await session_adapter.get_messages(
            session_id,
            limit=limit,
            after_timestamp=after,
        )

        return {
            "session_id": session_id,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "tool_calls": m.tool_calls,
                    "metadata": m.metadata,
                }
                for m in messages
            ],
            "count": len(messages),
        }
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error getting messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{user_id}/{session_id}")
async def delete_session(user_id: str, session_id: str):
    """Delete a session and its messages.

    Args:
        user_id: User identifier.
        session_id: Session identifier.

    Returns:
        Success status.
    """
    try:
        session_adapter: TroiseMainAdapter = container.resolve(TroiseMainAdapter)

        # Verify session belongs to user
        session = await session_adapter.get_session(user_id, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        await session_adapter.delete_session(user_id, session_id)

        return {"success": True, "session_id": session_id}
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
