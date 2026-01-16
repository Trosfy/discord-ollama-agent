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

        # 1. Extract artifacts (chain of responsibility)
        artifacts = await self._artifact_chain.extract(
            result,
            artifact_requested,
            expected_filename,
        )

        # 2. Format text for interface (needed for artifact extraction even if streamed)
        formatted = self._formatter.format(result.content, result.metadata)

        # 3. Send text messages (skip if content was already streamed)
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

        # 4. Send file artifacts
        if artifacts:
            builder = self._get_builder(context)
            for artifact in artifacts:
                # Encode content as base64 for binary-safe transfer
                if isinstance(artifact.content, bytes):
                    base64_data = base64.b64encode(artifact.content).decode('utf-8')
                else:
                    base64_data = base64.b64encode(artifact.content.encode('utf-8')).decode('utf-8')

                if artifact.confidence >= self.CONFIDENCE_THRESHOLD:
                    # High confidence - send as file
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
                    response_info["artifacts_sent"] += 1
                else:
                    # Low confidence - send as suggestion
                    base_msg = {
                        "type": "file_suggestion",
                        "filename": artifact.filename,
                        "base64_data": base64_data,
                        "source": artifact.source,
                        "confidence": artifact.confidence,
                        "needs_confirmation": True,
                    }
                    msg = builder.build_message(base_msg, context)
                    await websocket.send_json(msg)
                    response_info["artifacts_suggested"] += 1

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
