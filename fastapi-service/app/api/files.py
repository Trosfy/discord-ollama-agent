"""
File Upload API - Web UI

Handles file uploads from the web frontend.
Returns file references that can be included in chat messages.

SOLID Principles:
- Single Responsibility: Only handles HTTP file upload
- Open/Closed: Uses existing FileService (reuses Discord file processing)
- Dependency Inversion: Depends on FileService abstraction
"""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import List, Optional
from pydantic import BaseModel

from app.dependencies import get_file_service

logger = logging.getLogger(__name__)
router = APIRouter()


class FileUploadResponse(BaseModel):
    """Response for a single file upload."""
    file_id: str
    filename: str
    content_type: str
    size: int
    storage_path: str
    extracted_content: Optional[str] = None
    url: str = ""  # URL to access file (if applicable)
    status: str = "success"  # success or error


class FileUploadError(BaseModel):
    """Error for a single file upload."""
    filename: str
    error: str


class MultiFileUploadResponse(BaseModel):
    """Response for multiple file uploads."""
    success: bool = True
    file_refs: List[FileUploadResponse]
    errors: List[FileUploadError]


@router.post("/upload", response_model=MultiFileUploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    user_id: str = Form(default="webui_user"),
):
    """
    Upload one or more files for use in chat messages.
    
    Files are processed (OCR for images, text extraction for documents)
    and stored temporarily. Returns file references to include in messages.
    
    Args:
        files: List of files to upload
        user_id: User ID for tracking (from auth in future)
    
    Returns:
        MultiFileUploadResponse with file references and any errors
    """
    logger.info(f"📤 Received {len(files)} file(s) for upload from user {user_id}")
    
    file_service = get_file_service()
    uploaded_files: List[FileUploadResponse] = []
    errors: List[FileUploadError] = []
    
    for upload_file in files:
        try:
            # Validate file size (10MB max)
            MAX_SIZE = 10 * 1024 * 1024  # 10MB
            
            # Read file content
            file_data = await upload_file.read()
            
            if len(file_data) > MAX_SIZE:
                errors.append(FileUploadError(filename=upload_file.filename or "unnamed", error="File too large (max 10MB)"))
                continue
            
            if len(file_data) == 0:
                errors.append(FileUploadError(filename=upload_file.filename or "unnamed", error="Empty file"))
                continue
            
            # Process and save file using existing FileService
            file_info = await file_service.save_temp_file(
                file_data=file_data,
                filename=upload_file.filename or "unnamed",
                content_type=upload_file.content_type or "application/octet-stream",
                user_id=user_id
            )
            
            uploaded_files.append(FileUploadResponse(
                file_id=file_info["file_id"],
                filename=file_info["filename"],
                content_type=file_info["content_type"],
                size=file_info["size"],
                storage_path=file_info["storage_path"],
                extracted_content=file_info.get("extracted_content")
            ))
            
            logger.info(f"✅ Uploaded: {upload_file.filename} → {file_info['file_id']}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Upload failed: {upload_file.filename}: {error_msg}")
            errors.append(FileUploadError(filename=upload_file.filename or "unnamed", error=error_msg))
    
    return MultiFileUploadResponse(success=True, file_refs=uploaded_files, errors=errors)


@router.delete("/{file_id}")
async def delete_file(file_id: str):
    """
    Delete a previously uploaded file.
    
    Args:
        file_id: The file ID to delete
    
    Returns:
        Success message
    """
    try:
        file_service = get_file_service()
        await file_service.delete_file(file_id)
        logger.info(f"🗑️ Deleted file: {file_id}")
        return {"success": True, "message": f"File {file_id} deleted"}
    except Exception as e:
        logger.error(f"❌ Delete failed for {file_id}: {e}")
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
