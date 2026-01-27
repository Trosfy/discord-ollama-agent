"""Response handler for TROISE AI.

Coordinates postprocessing and response formatting:
1. Run artifact extraction chain (if output requested)
2. Format text for interface (Discord split, etc.)
3. Send messages + file artifacts via WebSocket
"""
import base64
import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.adapters.websocket.factory import get_message_builder

if TYPE_CHECKING:
    from fastapi import WebSocket
    from app.core.executor import ExecutionResult
    from app.core.context import ExecutionContext
    from app.adapters.formatters.interface import IResponseFormatter
    from app.postprocessing.artifact_chain import ArtifactExtractionChain, Artifact
    from app.core.interfaces.websocket import IWebSocketMessageBuilder

logger = logging.getLogger(__name__)


class ResponseHandler:
    """Coordinates postprocessing and response formatting.

    Responsibilities:
    1. Run artifact extraction chain (if output requested)
    2. Format text for interface (Discord split, etc.)
    3. Send messages + file artifacts via WebSocket

    Example:
        handler = ResponseHandler(formatter, artifact_chain)

        await handler.send_response(
            result=execution_result,
            context=context,
            artifact_requested=True,
            expected_filename="output.py",
        )
    """

    # Confidence threshold for automatic artifact sending
    CONFIDENCE_THRESHOLD = 0.7

    def __init__(
        self,
        formatter: "IResponseFormatter",
        artifact_chain: "ArtifactExtractionChain",
    ):
        """Initialize response handler.

        Args:
            formatter: Response formatter for the interface.
            artifact_chain: Chain for artifact extraction.
        """
        self._formatter = formatter
        self._artifact_chain = artifact_chain

    def _get_builder(self, context: "ExecutionContext") -> "IWebSocketMessageBuilder":
        """Get interface-appropriate message builder.

        Args:
            context: Execution context with interface type.

        Returns:
            Message builder for the interface.
        """
        return get_message_builder(context)

    async def send_response(
        self,
        result: "ExecutionResult",
        context: "ExecutionContext",
        artifact_requested: bool,
        expected_filename: Optional[str] = None,
        streamed: bool = False,
    ) -> Dict[str, Any]:
        """Process and send response.

        Args:
            result: Execution result from skill/agent.
            context: Execution context with WebSocket.
            artifact_requested: Whether user wants file output.
            expected_filename: Expected output filename.
            streamed: If True, text was already sent via streaming - skip text response.

        Returns:
            Dict with sent messages and artifacts info.
        """
        websocket = context.websocket
        if not websocket:
            logger.warning("No WebSocket connection for response")
            return {"error": "No WebSocket connection"}

        response_info = {
            "messages_sent": 0,
            "artifacts_sent": 0,
            "artifacts_suggested": 0,
        }

        # 1. Set context on handlers that need it (e.g., ImageArtifactHandler)
        for handler in self._artifact_chain._handlers:
            if hasattr(handler, 'set_context'):
                handler.set_context(context)

        # Log context state for debugging image pipeline
        logger.info(f"[POSTPROCESS] Context has {len(context.generated_images)} generated images")
        if context.generated_images:
            for img in context.generated_images:
                logger.info(f"[POSTPROCESS]   file_id={img.get('file_id')}, storage_key={img.get('storage_key')}")

        # 2. Extract artifacts (chain of responsibility)
        artifacts = await self._artifact_chain.extract(
            result,
            artifact_requested,
            expected_filename,
        )

        # Log extraction results for debugging image pipeline
        logger.info(f"[POSTPROCESS] Extracted {len(artifacts)} artifact(s)")
        for art in artifacts:
            size = len(art.content) if isinstance(art.content, bytes) else len(art.content.encode())
            logger.info(f"[POSTPROCESS]   {art.filename} ({size} bytes, source={art.source})")

        # 3. Format text for interface (needed for artifact extraction even if streamed)
        formatted = self._formatter.format(result.content, result.metadata)

        # 4. Send text messages (skip if content was already streamed)
        if not streamed:
            builder = self._get_builder(context)
            for i, msg_content in enumerate(formatted.messages):
                base_msg = {
                    "type": "response",
                    "content": msg_content,
                    "part": i + 1 if len(formatted.messages) > 1 else None,
                    "total_parts": len(formatted.messages) if len(formatted.messages) > 1 else None,
                    "source": {
                        "type": result.source_type,
                        "name": result.source_name,
                    },
                }
                msg = builder.build_message(base_msg, context)
                await websocket.send_json(msg)
                response_info["messages_sent"] += 1

        # 5. Send file artifacts
        if artifacts:
            builder = self._get_builder(context)
            for artifact in artifacts:
                # Check if this is a reference artifact (empty content with storage_key)
                storage_key = artifact.metadata.get("storage_key") if artifact.metadata else None
                is_reference = storage_key and isinstance(artifact.content, bytes) and len(artifact.content) == 0

                if is_reference:
                    # Reference artifact - send storage_key, interface fetches from MinIO
                    base_msg = {
                        "type": "file",
                        "filename": artifact.filename,
                        "storage_key": storage_key,
                        "source": artifact.source,
                        "confidence": artifact.confidence,
                    }
                else:
                    # Regular artifact - encode content as base64
                    if isinstance(artifact.content, bytes):
                        base64_data = base64.b64encode(artifact.content).decode('utf-8')
                    else:
                        base64_data = base64.b64encode(artifact.content.encode('utf-8')).decode('utf-8')

                    base_msg = {
                        "type": "file",
                        "filename": artifact.filename,
                        "filepath": artifact.filepath,
                        "base64_data": base64_data,
                        "source": artifact.source,
                        "confidence": artifact.confidence,
                    }

                if artifact.confidence >= self.CONFIDENCE_THRESHOLD:
                    # High confidence - send as file
                    msg = builder.build_message(base_msg, context)
                    try:
                        logger.info(f"[POSTPROCESS] Sending file: {artifact.filename}, storage_key={storage_key}")
                        await websocket.send_json(msg)
                        response_info["artifacts_sent"] += 1
                    except Exception as e:
                        logger.error(f"[POSTPROCESS] Failed to send file artifact: {e}")
                        # Don't re-raise - continue with other artifacts
                else:
                    # Low confidence - send as suggestion
                    base_msg["type"] = "file_suggestion"
                    base_msg["needs_confirmation"] = True
                    msg = builder.build_message(base_msg, context)
                    try:
                        await websocket.send_json(msg)
                        response_info["artifacts_suggested"] += 1
                    except Exception as e:
                        logger.error(f"[POSTPROCESS] Failed to send file suggestion: {e}")

        return response_info

    async def send_error(
        self,
        error: str,
        context: "ExecutionContext",
    ) -> None:
        """Send error message.

        Args:
            error: Error message.
            context: Execution context with WebSocket.
        """
        websocket = context.websocket
        if websocket:
            builder = self._get_builder(context)
            msg = builder.build_message(
                {"type": "error", "content": error},
                context,
            )
            await websocket.send_json(msg)

    async def send_artifact_only(
        self,
        artifact: "Artifact",
        context: "ExecutionContext",
    ) -> None:
        """Send a single artifact without text response.

        Args:
            artifact: Artifact to send.
            context: Execution context with WebSocket.
        """
        websocket = context.websocket
        if websocket:
            # Encode content as base64 for binary-safe transfer
            if isinstance(artifact.content, bytes):
                base64_data = base64.b64encode(artifact.content).decode('utf-8')
            else:
                base64_data = base64.b64encode(artifact.content.encode('utf-8')).decode('utf-8')

            builder = self._get_builder(context)
            base_msg = {
                "type": "file",
                "filename": artifact.filename,
                "filepath": artifact.filepath,
                "base64_data": base64_data,
                "source": artifact.source,
                "confidence": artifact.confidence,
            }
            msg = builder.build_message(base_msg, context)
            await websocket.send_json(msg)
