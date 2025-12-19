"""Output artifact creation strategy using thinking model for intelligent post-processing."""
import sys
sys.path.insert(0, '/shared')

import re
import json
import aiohttp
import asyncio
import uuid
from typing import Dict, List
from strands import Agent
from strands.models.ollama import OllamaModel
from app.interfaces.processing_strategy import ProcessingStrategy
from app.utils.model_utils import get_ollama_keep_alive
from app.prompts import PromptComposer
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class OutputArtifactStrategy(ProcessingStrategy):
    """Strategy for creating output artifacts (Single Responsibility)."""

    def __init__(self, ollama_host: str, model: str = "gpt-oss:20b"):
        """
        Initialize output artifact strategy.

        Args:
            ollama_host: URL of Ollama API server
            model: Thinking model to use for intelligent extraction (default: gpt-oss:20b)
        """
        self.ollama_host = ollama_host
        self.model = model

        # Initialize PromptComposer (modular prompt system)
        self.prompt_composer = PromptComposer()
        self.extraction_prompt = self.prompt_composer.get_extraction_prompt()

        self.keep_alive = get_ollama_keep_alive()  # Get from config for consistency

        logger.info(f"✅ OutputArtifactStrategy initialized with model: {self.model}")
        logger.info("✅ Extraction prompt loaded from JSON config")

    async def process(self, context: Dict) -> List[Dict]:
        """
        Extract artifacts from LLM response and create files.

        Context contains:
            - user_message: Original user message
            - llm_response: LLM's response
            - file_service: FileService instance

        Returns:
            List of created artifact metadata
        """
        user_message = context.get('user_message', '')
        llm_response = context.get('llm_response', '')
        file_service = context.get('file_service')

        if not file_service:
            logger.error("❌ FileService not provided in context")
            return []

        logger.info(f"📋 Extracting artifact details using {self.model}")

        # Use thinking model to intelligently extract, filter, complete, and reformat artifacts
        artifact_data = await self._extract_artifact_data(user_message, llm_response)

        if not artifact_data or not artifact_data.get('filename'):
            logger.info("ℹ️  No artifact to create")
            return []

        # Create artifact
        try:
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
                'type': artifact_data.get('artifact_type', 'text'),  # Defensive: default to 'text'
                'status': 'created'
            }

            logger.info(f"📦 Created artifact: {artifact_data['filename']} ({len(artifact_data['content'])} bytes)")
            return [artifact_metadata]

        except Exception as e:
            logger.error(f"❌ Failed to create artifact: {e}")
            return []

    async def _extract_artifact_data(self, user_message: str, llm_response: str) -> Dict:
        """
        Use thinking model to intelligently extract, filter, complete, and reformat artifact from conversation.

        Args:
            user_message: User's request
            llm_response: LLM's response

        Returns:
            Dict with filename, content, artifact_type (or empty dict)
        """
        # Build conversation context for extraction
        conversation = f"""USER REQUEST: {user_message}

ASSISTANT RESPONSE: {llm_response}"""

        # Build full prompt
        prompt = f"{self.extraction_prompt}\n\n{conversation}"

        try:
            # Create OllamaModel for deterministic extraction (no thinking mode)
            ollama_model = OllamaModel(
                host=self.ollama_host,
                model_id=self.model,
                temperature=0.1,  # Low temperature for consistent parsing
                keep_alive=self.keep_alive
            )

            # Create agent (no tools needed for extraction)
            agent = Agent(
                model=ollama_model,
                tools=[]
            )

            # Run agent in executor (Strands pattern for sync API)
            loop = asyncio.get_event_loop()
            agent_result = await loop.run_in_executor(None, agent, prompt)

            # Convert AgentResult to string (same pattern as strands_llm.py:303, 417)
            response_text = str(agent_result)

            # Log response for debugging
            logger.info(f"📝 Post-processor raw response (first 500 chars): {response_text[:500]}")

            # Parse JSON response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                logger.warning(f"⚠️  No JSON found in response: {response_text[:100]}")
                return {}

            json_str = json_match.group()
            logger.info(f"📝 Extracted JSON string (first 500 chars): {json_str[:500]}")

            try:
                artifact_data = json.loads(json_str)
                logger.info(f"✅ Successfully parsed JSON from {self.model}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ JSON parsing failed: {e}")
                logger.error(f"📝 {self.model} returned invalid JSON. Raw response: {json_str[:500]}")
                logger.error("⚠️  Model did not follow the CRITICAL JSON escaping instructions!")
                return {}

            if not artifact_data.get('filename'):
                logger.info("ℹ️  No artifact needed")
                return {}

            # Defensive check: default to 'text' if artifact_type is missing
            artifact_type = artifact_data.get('artifact_type', 'text')
            logger.info(f"✅ Extracted artifact: {artifact_data['filename']} ({artifact_type})")
            return artifact_data

        except Exception as e:
            import traceback
            logger.error(f"❌ Artifact extraction error: {type(e).__name__}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {}
