"""Post-processing service for automatic artifact creation using LLM."""
import sys
sys.path.insert(0, '/shared')

import re
import aiohttp
from typing import Dict, List, Optional, Tuple
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class ArtifactPostProcessor:
    """Post-processes LLM responses to automatically create artifacts using ministral."""

    def __init__(self, ollama_host: str, model: str = "ministral-3:14b"):
        """
        Initialize artifact post-processor.

        Args:
            ollama_host: URL of Ollama API server
            model: Model to use for post-processing (default: ministral-3:14b)
        """
        self.ollama_host = ollama_host
        self.model = model
        logger.info(f"✅ ArtifactPostProcessor initialized with model: {self.model}")

    async def should_create_artifact(
        self,
        user_message: str,
        llm_response: str
    ) -> Optional[Dict[str, str]]:
        """
        Determine if artifact should be created and extract details.

        Uses ministral to analyze the user's request and LLM response.

        Args:
            user_message: Original user message
            llm_response: LLM's response

        Returns:
            Dict with artifact details if artifact should be created, None otherwise
            Dict contains: filename, content, artifact_type
        """
        # Quick check: Does user message contain file creation keywords?
        file_keywords = [
            'create a file', 'make a file', 'generate a file',
            'create a python file', 'create a javascript file',
            'create me a', 'save to file', 'write a file',
            'create script', 'make script'
        ]

        if not any(keyword in user_message.lower() for keyword in file_keywords):
            return None

        # Quick check: Does response contain code blocks?
        if '```' not in llm_response:
            return None

        logger.info("📋 Detected file creation request with code block, using LLM for extraction")

        # Use ministral to extract artifact details
        prompt = f"""Analyze this conversation and extract file creation details.

USER REQUEST: {user_message}

ASSISTANT RESPONSE: {llm_response}

TASK: If the user requested file creation and the response contains code, extract:
1. Filename with appropriate extension (e.g., "quicksort.py", "config.json", "README.md")
2. The complete code/content from the code block
3. Artifact type: "code" for programming files, "data" for JSON/config, "text" for documentation

Respond ONLY with a JSON object in this EXACT format:
{{"filename": "example.py", "content": "the full code here", "artifact_type": "code"}}

If no file should be created, respond with:
{{"filename": null}}

Remember:
- Extract the FULL content from the code block, not just a summary
- Choose appropriate file extension based on the code language
- For Python use .py, JavaScript use .js, TypeScript use .ts, etc.
- Only include the JSON object, nothing else"""

        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.1  # Low temperature for consistent parsing
                }

                async with session.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"❌ Artifact extraction failed: {error_text}")
                        return None

                    result = await resp.json()
                    response_text = result.get('response', '').strip()

            # Parse JSON response
            import json

            # Extract JSON from response (in case model added extra text)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                logger.warning(f"⚠️  No JSON found in response: {response_text[:100]}")
                return None

            artifact_data = json.loads(json_match.group())

            if not artifact_data.get('filename'):
                logger.info("ℹ️  LLM determined no artifact should be created")
                return None

            logger.info(f"✅ Extracted artifact: {artifact_data['filename']} ({artifact_data['artifact_type']})")
            return artifact_data

        except Exception as e:
            logger.error(f"❌ Artifact extraction error: {e}")
            return None

    async def create_artifacts_if_needed(
        self,
        user_message: str,
        llm_response: str,
        file_service
    ) -> List[Dict]:
        """
        Create artifacts if needed based on user request and LLM response.

        Args:
            user_message: Original user message
            llm_response: LLM's response
            file_service: FileService instance for saving artifacts

        Returns:
            List of created artifact metadata dicts
        """
        artifact_data = await self.should_create_artifact(user_message, llm_response)

        if not artifact_data:
            return []

        try:
            import uuid
            artifact_id = str(uuid.uuid4())

            # Save artifact
            storage_path = await file_service.save_artifact(
                artifact_id=artifact_id,
                content=artifact_data['content'],
                filename=artifact_data['filename']
            )

            artifact_metadata = {
                'artifact_id': artifact_id,
                'filename': artifact_data['filename'],
                'storage_path': storage_path,
                'size': str(len(artifact_data['content'])),
                'type': artifact_data['artifact_type'],
                'status': 'created'
            }

            logger.info(f"📦 Created artifact: {artifact_data['filename']} ({len(artifact_data['content'])} bytes)")
            return [artifact_metadata]

        except Exception as e:
            logger.error(f"❌ Failed to create artifact: {e}")
            return []
