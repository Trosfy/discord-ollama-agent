"""File handling tools for Strands Agent."""
import sys
sys.path.insert(0, '/shared')

from strands import tool
from typing import List, Dict
import logging_client
import asyncio
import uuid

# Initialize logger
logger = logging_client.setup_logger('fastapi')


@tool(
    name="list_attachments",
    description="""List all files attached to the current message with their EXTRACTED CONTENT.

Returns file metadata AND the pre-extracted text content from preprocessing.
- Images: OCR-extracted text
- PDFs: Extracted text
- Text/code files: File contents

Use this tool to access uploaded file contents - DO NOT use file_read for user uploads."""
)
def list_attachments() -> List[Dict[str, str]]:
    """
    List all files attached to the user's message with extracted content.

    Returns:
        List of dicts, each containing:
        - file_id: Unique identifier
        - filename: Original filename
        - content_type: MIME type
        - size: File size in bytes
        - extracted_content: Pre-extracted text from preprocessing (OCR for images, direct read for text/PDF)
    """
    from app.dependencies import get_current_request

    request = get_current_request()
    file_refs = request.get('file_refs', [])

    result = []
    for ref in file_refs:
        file_info = {
            'file_id': ref['file_id'],
            'filename': ref['filename'],
            'content_type': ref['content_type'],
            'size': str(ref['size']),
            'extracted_content': ref.get('extracted_content', '[No content extracted]')
        }
        result.append(file_info)

    logger.info(f"📎 Tool: list_attachments | Found {len(result)} file(s)")
    return result


# ==============================================================================
# DEPRECATED TOOLS - No longer registered
# ==============================================================================
# These tools have been replaced:
# - get_file_content → list_attachments (pre-extracted content from preprocessing)
# - create_artifact → file_write_wrapped (Strands + DiscordExtension for post-processing)
#
# Kept for reference only. Not exported in __init__.py
# ==============================================================================

@tool(
    name="get_file_content",
    description="DEPRECATED - Use file_read instead. Get the extracted text/content from a specific attached file using its file_id. Use list_attachments first to see available files."
)
def get_file_content(file_id: str) -> Dict[str, str]:
    """
    Retrieve extracted content from an attached file.

    Args:
        file_id: ID of the file (from list_attachments)

    Returns:
        Dict containing:
        - filename: Original filename
        - content_type: MIME type
        - extracted_content: Text extracted from the file (OCR for images, direct read for text files)
        - error: Error message if file not found
    """
    from app.dependencies import get_current_request

    request = get_current_request()
    file_refs = request.get('file_refs', [])

    for ref in file_refs:
        if ref['file_id'] == file_id:
            logger.info(f"📄 Tool: get_file_content | File: {ref['filename']}")
            return {
                'filename': ref['filename'],
                'content_type': ref['content_type'],
                'extracted_content': ref.get('extracted_content', '[No content extracted]')
            }

    logger.warning(f"❌ Tool: get_file_content | File {file_id} not found")
    return {'error': f"File {file_id} not found in uploaded attachments"}


@tool(
    name="create_artifact",
    description="""Create a downloadable file artifact when user requests file creation.

WHEN TO USE:
- User says: "create a [language] file", "generate a script", "make a config", "save to file"
- User wants: Downloadable code, data, or documentation files
- Keywords: "create file", "generate file", "make file", "save as"

IMPORTANT: This is the ONLY way to create files. Do NOT generate file:// download links.
The file will be automatically attached to Discord message.

Returns artifact metadata with downloadable file for user."""
)
def create_artifact(
    content: str,
    filename: str,
    artifact_type: str = "text"
) -> Dict[str, str]:
    """
    Create a downloadable artifact file for the user.

    IMPORTANT: Only call this tool when the user explicitly requests a file output
    or downloadable artifact. Do NOT use for normal responses.

    Args:
        content: The artifact content (code, data, text, etc.)
        filename: Desired filename (e.g., "script.py", "data.json", "README.md")
        artifact_type: Type hint - "code", "data", "diagram", "text" (for metadata)

    Returns:
        Dict containing:
        - artifact_id: Unique identifier
        - filename: Filename as provided
        - size: Size in bytes
        - type: Artifact type
        - status: "created" or "error"
    """
    from app.dependencies import get_file_service

    try:
        file_service = get_file_service()
        artifact_id = str(uuid.uuid4())

        # Save artifact to temp storage (12 hours TTL)
        storage_path = asyncio.run(
            file_service.save_artifact(
                artifact_id=artifact_id,
                content=content,
                filename=filename
            )
        )

        logger.info(f"📦 Tool: create_artifact | Created {filename} ({len(content)} bytes)")

        # Register artifact in current request context (for orchestrator to collect)
        artifact_metadata = {
            'artifact_id': artifact_id,
            'filename': filename,
            'storage_path': storage_path,
            'size': str(len(content)),
            'type': artifact_type,
            'status': 'created'
        }

        try:
            from app.dependencies import get_current_request
            current_request = get_current_request()
            if 'artifacts_created' not in current_request:
                current_request['artifacts_created'] = []
            current_request['artifacts_created'].append(artifact_metadata)
            logger.debug(f"📎 Registered artifact {artifact_id} in request context")
        except Exception as e:
            logger.warning(f"⚠️  Failed to register artifact in request context: {e}")

        return artifact_metadata

    except Exception as e:
        logger.error(f"❌ Tool: create_artifact | Error: {str(e)}")
        return {
            'error': f"Failed to create artifact: {str(e)}",
            'status': 'error'
        }
