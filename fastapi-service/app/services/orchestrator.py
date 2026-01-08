"""Main orchestration service coordinating all business logic."""
import sys
sys.path.insert(0, '/shared')

import asyncio
from typing import Dict
import re
import uuid

from app.config import settings, get_model_capabilities, get_active_profile
from app.interfaces.storage import IConversationStorage, IUserStorage
from app.interfaces.llm import LLMInterface
from app.services.context_manager import ContextManager
from app.services.token_tracker import TokenTracker
from app.services.summarization_service import SummarizationService
from app.services.router_service import RouterService
from app.utils.model_utils import force_unload_model
from app.preprocessing import FileContextBuilder
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


def inject_reference_urls(text: str, references: list) -> str:
    """
    Replace inline 【title】 citations with markdown [title](url) links.

    Args:
        text: Response text with 【】 citations
        references: List of {'title': str, 'url': str} dicts

    Returns:
        Text with 【】 replaced by markdown links
    """
    if not references:
        return text

    # Create lookup dict (case-insensitive, normalized)
    ref_lookup = {}
    for ref in references:
        title = ref['title']
        # Normalize: lowercase, strip whitespace
        normalized = title.lower().strip()
        ref_lookup[normalized] = ref['url']

    def replace_citation(match):
        citation_text = match.group(1)  # Text inside 【】
        normalized = citation_text.lower().strip()

        # Try exact match first
        if normalized in ref_lookup:
            url = ref_lookup[normalized]
            return f"[{citation_text}]({url})"

        # Try partial match (citation contains ref title or vice versa)
        for ref_title, url in ref_lookup.items():
            if ref_title in normalized or normalized in ref_title:
                return f"[{citation_text}]({url})"

        # No match found - leave as is but log warning
        logger.warning(f"⚠️  No URL found for citation: 【{citation_text}】")
        return match.group(0)  # Return original 【text】

    # Replace all 【...】 patterns
    result = re.sub(r'【([^】]+)】', replace_citation, text)

    return result


class Orchestrator:
    """Coordinates all services without containing business logic (SOLID)."""

    def __init__(
        self,
        conversation_storage: IConversationStorage,
        user_storage: IUserStorage,
        llm: LLMInterface,
        context_manager: ContextManager,
        token_tracker: TokenTracker,
        summarization_service: SummarizationService,
        router_service: RouterService,
        strategy_registry,  # NEW: Inject registry (DIP)
        profile_manager = None,  # NEW: Inject ProfileManager (DIP)
        preference_resolver = None  # NEW: Inject PreferenceResolver (DIP)
    ):
        """
        Initialize orchestrator with all required services.

        Args:
            conversation_storage: Conversation storage for messages
            user_storage: User storage for preferences and tokens
            llm: LLM interface for generation
            context_manager: Context retrieval service
            token_tracker: Token management service
            summarization_service: Summarization service
            router_service: Router service for request classification
            strategy_registry: Strategy registry for postprocessing
            profile_manager: ProfileManager for circuit breaker fallback (optional)
            preference_resolver: PreferenceResolver for unified model preference handling
        """
        self.conversation_storage = conversation_storage
        self.user_storage = user_storage
        self.llm = llm
        self.context_manager = context_manager
        self.token_tracker = token_tracker
        self.summarization_service = summarization_service
        self.router_service = router_service
        self.strategy_registry = strategy_registry
        self.profile_manager = profile_manager
        self.preference_resolver = preference_resolver
        self.file_context_builder = FileContextBuilder()  # SOLID: Extract preprocessing

    async def _resolve_route_config(
        self,
        request: Dict,
        user_prefs: Dict,
        file_refs: list,
        user_message_content: str,
        source: str
    ) -> tuple:
        """
        Single entry point for route resolution (DRY principle).

        Uses PreferenceResolver to unify preference handling across all interfaces.
        Artifact detection runs regardless of routing bypass.

        Args:
            request: Request dictionary
            user_prefs: User preferences from storage
            file_refs: List of file references
            user_message_content: Message with file context appended
            source: Source of request ('discord' or 'webui')

        Returns:
            Tuple of (route_config, resolved_preferences)
        """
        from app.services.preference_resolver import ResolvedPreferences

        # Use PreferenceResolver if available, otherwise fall back to legacy logic
        if self.preference_resolver:
            resolved = self.preference_resolver.resolve(request, user_prefs)

            if resolved.should_bypass_routing:
                # Bypass routing but STILL run artifact detection
                output_artifact = await self.router_service.output_detector.detect(
                    user_message_content,
                    model=resolved.artifact_detection_model
                )

                # Check for input artifacts (deterministic)
                input_artifact = len(file_refs) > 0

                route_config = {
                    'route': 'SELF_HANDLE',
                    'model': resolved.model,
                    'mode': 'single',
                    'preprocessing': ['INPUT_ARTIFACT'] if input_artifact else [],
                    'postprocessing': ['OUTPUT_ARTIFACT'] if output_artifact else [],
                    'source': source,
                    'user_selected_model': True
                }
                logger.info(f"Bypassed routing via {resolved.model_source}: {resolved.model}")
            else:
                # Full routing with artifact detection
                route_config = await self.router_service.classify_request(
                    user_message=user_message_content,
                    file_refs=file_refs,
                    artifact_detection_model=resolved.artifact_detection_model
                )
                route_config['source'] = source
                logger.info(f"Routed to: {route_config['route']} via router")

            return route_config, resolved
        else:
            # Legacy fallback (no PreferenceResolver)
            logger.warning("PreferenceResolver not configured - using legacy routing")
            return None, None

    async def process_request(
        self,
        request: Dict,
        route_config: Dict = None  # NEW: Optional param to skip routing
    ) -> Dict:
        """
        Main request processing flow.

        Steps:
        1. Check for simple greetings (save LLM costs)
        2. Get user and check token budget
        3. Load thread context
        4. Check if summarization needed
        5. Generate response via Strands
        6. Save to database
        7. Update token usage

        Args:
            request: Request dictionary with user_id, conversation_id, message, etc.
            route_config: Optional route config to skip routing (for retries)

        Returns:
            Result dictionary with response, tokens_used, model

        Raises:
            Exception: If token budget exceeded or generation fails
        """
        # Step 0: Check if we can recover from fallback (ProfileManager health check)
        if self.profile_manager:
            await self.profile_manager.check_and_recover()

        # Log incoming request
        logger.info(f"📥 Processing request from user {request['user_id']}: {request['message']}")

        # Step 1: Get user data (preferences + tokens)
        user_prefs = await self.user_storage.get_user_preferences(request['user_id'])
        user_tokens = await self.user_storage.get_user_tokens(request['user_id'])

        if not user_prefs or not user_tokens:
            # Create new user
            await self.user_storage.create_user(
                user_id=request['user_id'],
                discord_username=f"user_{request['user_id'][:8]}",
                user_tier='free'
            )
            user_prefs = await self.user_storage.get_user_preferences(request['user_id'])
            user_tokens = await self.user_storage.get_user_tokens(request['user_id'])

        # Step 3: Check token budget (if enabled)
        if not settings.DISABLE_TOKEN_BUDGET:
            if not await self.token_tracker.has_budget(
                user_tokens,
                request['estimated_tokens']
            ):
                raise Exception(
                    f"Token budget exceeded. Remaining: {user_tokens['tokens_remaining']}"
                )

        # Step 4: Load conversation context
        context = await self.context_manager.get_conversation_context(
            request['conversation_id'],
            request['user_id']
        )

        # Step 5: Check if summarization needed
        total_tokens = sum(msg['token_count'] for msg in context)
        if total_tokens > user_prefs['auto_summarize_threshold']:
            context = await self.summarization_service.summarize_and_prune(
                conversation_id=request['conversation_id'],
                messages=context,
                user_id=request['user_id']
            )

        # Step 6: Build enriched message with file context (SOLID preprocessing)
        file_refs = request.get('file_refs', [])
        user_message_content = self.file_context_builder.append_to_message(
            request['message'],
            file_refs
        )

        user_message = {
            'role': 'user',
            'content': user_message_content
        }
        context.append(user_message)

        # Step 7: Set current request context (for tools to access file_refs)
        from app.dependencies import set_current_request
        set_current_request(request)

        # Step 8: Resolve routing using PreferenceResolver (unified preference handling)
        source = request.get('metadata', {}).get('source', 'discord')
        resolved_prefs = None  # Will hold ResolvedPreferences if PreferenceResolver is used

        if route_config is None:
            route_config, resolved_prefs = await self._resolve_route_config(
                request=request,
                user_prefs=user_prefs,
                file_refs=file_refs,
                user_message_content=user_message_content,
                source=source
            )

            # Legacy fallback if PreferenceResolver not configured
            if route_config is None:
                # Fall back to old routing logic
                preferred_model = user_prefs.get('preferred_model')
                if preferred_model:
                    route_config = {
                        'route': 'SELF_HANDLE',
                        'model': preferred_model,
                        'mode': 'single',
                        'preprocessing': ['INPUT_ARTIFACT'] if len(file_refs) > 0 else [],
                        'postprocessing': [],
                        'source': source
                    }
                else:
                    route_config = await self.router_service.classify_request(
                        user_message=user_message_content,
                        file_refs=file_refs
                    )
                    route_config['source'] = source
        else:
            logger.info(f"Reusing route config: {route_config['route']}")

        # Get temperature from resolved preferences or fall back to user_prefs
        if resolved_prefs:
            temperature = resolved_prefs.temperature
        else:
            # Legacy fallback
            temperature = user_prefs.get('temperature')
            if temperature is None:
                temperature = settings.DEFAULT_TEMPERATURE
            else:
                temperature = float(temperature)

        # Step 9: Smart router reuse logic (check if we can reuse router for SELF_HANDLE)
        # NOTE: This is only needed when router is a SEPARATE model from execution model
        # In performance profile, router == execution model (gpt-oss:120b), so no special handling needed
        if route_config['route'] == 'SELF_HANDLE' and route_config['model'] == settings.ROUTER_MODEL:
            # Router model will be used for execution - it just stays loaded
            # No need to unload/reload when router == execution model
            logger.debug(f"✅ Reusing {settings.ROUTER_MODEL} for SELF_HANDLE (router == execution model)")
        elif route_config['route'] != 'SELF_HANDLE':
            # Different model needed - unload router (conservative mode only)
            if settings.VRAM_CONSERVATIVE_MODE:
                await force_unload_model(settings.ROUTER_MODEL)
                logger.debug(f"🔽 Conservative mode: Unloaded router to load {route_config['model']}")
            else:
                profile_name = get_active_profile().profile_name.title()
                logger.debug(f"💤 {profile_name} profile: Router + {route_config['model']} can coexist (orchestrator manages eviction)")

        # Step 10: Use filtered prompt for main LLM if available (clean file language)
        # NOTE: OCR preprocessing removed - file content already in user_message_content via FileContextBuilder
        if route_config.get('filtered_prompt'):
            # Replace last message (user message) with filtered version for LLM
            context[-1]['content'] = route_config['filtered_prompt']
            logger.debug(f"🧹 Using filtered prompt for main LLM: {route_config['filtered_prompt'][:80]}...")

        response = await self.llm.generate_with_route(
            context=context,
            route_config=route_config,
            temperature=temperature,
            user_base_prompt=user_prefs.get('base_prompt'),
            user_thinking_enabled=resolved_prefs.thinking_enabled if resolved_prefs else user_prefs.get('thinking_enabled')
        )

        # Format and append references if present
        response_content = response['content']

        # Validate response is not empty
        if not response_content or not response_content.strip():
            logger.error(f"❌ LLM returned empty response for route {route_config.get('route')} with model {route_config.get('model')}")
            logger.error(f"   User thinking preference: {user_prefs.get('thinking_enabled')}, Temperature: {temperature}")
            raise Exception(f"LLM returned empty response (route: {route_config.get('route')}, model: {route_config.get('model')})")

        references = response.get('references', [])

        # Inject URLs into inline 【】 citations
        if references:
            response_content = inject_reference_urls(response_content, references)
            logger.debug(f"🔗 Injected URLs into {len(references)} inline citations")

        # Log generated response (replace newlines for clean single-line log)
        preview = response_content[:150].replace('\n', ' ').replace('\r', ' ')
        logger.info(f"📤 Generated response for user {request['user_id']}: {preview}{'...' if len(response_content) > 150 else ''}")

        # Note: References are now injected inline, no need for separate section
        # (The old code that appended references at the end is removed)

        # Step 8: Save messages to database
        await self.conversation_storage.add_message(
            conversation_id=request['conversation_id'],
            message_id=request['message_id'],
            role='user',
            content=request['message'],
            token_count=request['estimated_tokens'],
            user_id=request['user_id'],
            model_used=user_prefs.get('preferred_model') or 'trollama'
        )

        response_tokens = await self.token_tracker.count_tokens(
            response_content
        )

        await self.conversation_storage.add_message(
            conversation_id=request['conversation_id'],
            message_id=f"response_{request['message_id']}",
            role='assistant',
            content=response_content,
            token_count=response_tokens,
            user_id=request['user_id'],
            model_used=response['model']
        )

        # Step 8.5: Force unload main LLM if post-processing needed (conservative mode only)
        if 'OUTPUT_ARTIFACT' in route_config.get('postprocessing', []):
            if settings.VRAM_CONSERVATIVE_MODE:
                await force_unload_model(response['model'])
                logger.debug(f"🔽 Conservative mode: Unloaded {response['model']} before post-processing")
            else:
                profile_name = get_active_profile().profile_name.title()
                logger.debug(f"💤 {profile_name} profile: {response['model']} + extraction model can coexist")

        # Step 8.5: Apply postprocessing strategies
        for strategy_name in route_config.get('postprocessing', []):
            # Special handling for OUTPUT_ARTIFACT - use as fallback only
            if strategy_name == 'OUTPUT_ARTIFACT':
                artifacts_created = request.get('artifacts_created', [])

                # Check if tools already created artifacts
                if len(artifacts_created) > 0:
                    logger.info(f"✅ {len(artifacts_created)} artifact(s) created via tools - skipping extraction")
                    continue  # Tools worked - skip postprocessing

                # Fallback: Extract from response (for non-tool models or tool failures)
                logger.info("No artifacts from tools - attempting extraction fallback")

                # Determine extraction model from resolved preferences or profile fallback
                if resolved_prefs:
                    extraction_model = resolved_prefs.artifact_extraction_model
                    logger.info(f"Using profile artifact extraction model: {extraction_model}")
                else:
                    # Fallback: get directly from profile (should not happen with new code)
                    extraction_model = get_active_profile().artifact_extraction_model
                    logger.warning(f"⚠️  resolved_prefs is None - falling back to profile: {extraction_model}")

                # Create OutputArtifactStrategy
                from app.strategies.output_artifact_strategy import OutputArtifactStrategy
                strategy = OutputArtifactStrategy(
                    ollama_host=settings.OLLAMA_HOST,
                    model=extraction_model
                )

                # Execute extraction with profile-specific model
                from app.services.file_service import FileService
                extraction_context = {
                    'user_message': request['message'],
                    'llm_response': response_content,
                    'file_service': FileService(),
                    'extraction_model': extraction_model  # Pass model to strategy
                }

                artifacts_from_strategy = await strategy.process(extraction_context)

                if len(artifacts_from_strategy) > 0:
                    logger.info(f"✅ Extracted {len(artifacts_from_strategy)} artifact(s) via postprocessing fallback")
                    request['artifacts_created'] = artifacts_from_strategy
                else:
                    logger.warning(
                        f"⚠️  OUTPUT_ARTIFACT detected but no artifacts created (tools or extraction). "
                        f"User: {request['user_id']}, Message: {request['message'][:100]}"
                    )

                continue  # Done with OUTPUT_ARTIFACT

            # Execute other postprocessing strategies (if any)
            logger.info(f"📦 Applying {strategy_name} postprocessing")

            from app.services.file_service import FileService
            context = {
                'user_message': request['message'],
                'llm_response': response_content,
                'file_service': FileService()
            }

            artifacts_from_strategy = await self.strategy_registry.execute(
                strategy_name,
                context
            )

            # Merge with tool-created artifacts
            artifacts = request.get('artifacts_created', []) + artifacts_from_strategy
            request['artifacts_created'] = artifacts

        # Step 9: Update token usage
        total_tokens_used = request['estimated_tokens'] + response_tokens
        await self.token_tracker.update_usage(
            request['user_id'],
            total_tokens_used
        )

        # Step 10: Include artifacts in response (non-editing approach)
        # Artifacts are tracked via the context variable set earlier
        artifacts = request.get('artifacts_created', [])
        if artifacts:
            logger.info(f"📦 {len(artifacts)} artifact(s) created during request processing")
            # Note: Response content NOT edited - user receives full Discord preview + file

        # Step 11: Clean up temporary upload files
        if file_refs:
            from app.dependencies import get_file_service
            file_service = get_file_service()

            for file_ref in file_refs:
                storage_path = file_ref.get('storage_path')
                if storage_path:
                    try:
                        await file_service.delete_file(storage_path)
                        logger.info(f"🗑️  Cleaned up temp file: {file_ref['filename']}")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to clean up temp file {storage_path}: {e}")

        # Step 11: Force unload after SELF_HANDLE execution (conservative mode only)
        if route_config['route'] == 'SELF_HANDLE' and route_config['model'] == settings.ROUTER_MODEL:
            if settings.VRAM_CONSERVATIVE_MODE:
                # Conservative mode (16GB): Force-unload after each request
                await force_unload_model(settings.ROUTER_MODEL)
                logger.debug("🔽 Conservative mode: Unloaded router after SELF_HANDLE")
            else:
                # High-VRAM profiles (performance/balanced): Trust keep_alive + orchestrator
                profile_name = get_active_profile().profile_name.title()
                logger.debug(f"💤 {profile_name} profile: Router stays loaded (keep_alive=30m)")

        return {
            'request_id': request['request_id'],
            'response': response_content,
            'tokens_used': total_tokens_used,
            'model': response['model'],
            'artifacts': artifacts  # NEW: Include artifacts for Discord upload
        }

    async def process_request_stream(
        self,
        request: Dict,
        stream_callback
    ) -> Dict:
        """
        Process request with streaming response.

        Similar to process_request() but streams chunks progressively via callback.

        Args:
            request: Request dictionary with user_id, conversation_id, message, etc.
            stream_callback: Async callback function to receive chunks

        Returns:
            Result dictionary with final response, tokens_used, model, artifacts

        Raises:
            Exception: If token budget exceeded or generation fails
        """
        # Step 0: Check if we can recover from fallback (ProfileManager health check)
        if self.profile_manager:
            await self.profile_manager.check_and_recover()

        # Log incoming request
        logger.info(f"📥 Processing streaming request from user {request['user_id']}: {request['message']}")

        # Step 1: Get user data (preferences + tokens) - identical to process_request()
        user_prefs = await self.user_storage.get_user_preferences(request['user_id'])
        user_tokens = await self.user_storage.get_user_tokens(request['user_id'])

        if not user_prefs or not user_tokens:
            # Create new user
            await self.user_storage.create_user(
                user_id=request['user_id'],
                discord_username=f"user_{request['user_id'][:8]}",
                user_tier='free'
            )
            user_prefs = await self.user_storage.get_user_preferences(request['user_id'])
            user_tokens = await self.user_storage.get_user_tokens(request['user_id'])

        # Step 2: Check token budget (if enabled)
        if not settings.DISABLE_TOKEN_BUDGET:
            if not await self.token_tracker.has_budget(
                user_tokens,
                request['estimated_tokens']
            ):
                raise Exception(
                    f"Token budget exceeded. Remaining: {user_tokens['tokens_remaining']}"
                )

        # Step 3: Load conversation context
        context = await self.context_manager.get_conversation_context(
            request['conversation_id'],
            request['user_id']
        )

        # Step 4: Check if summarization needed
        total_tokens = sum(msg['token_count'] for msg in context)
        if total_tokens > user_prefs['auto_summarize_threshold']:
            context = await self.summarization_service.summarize_and_prune(
                conversation_id=request['conversation_id'],
                messages=context,
                user_id=request['user_id']
            )

        # Step 5: Build enriched message with file context (SOLID preprocessing)
        file_refs = request.get('file_refs', [])
        user_message_content = self.file_context_builder.append_to_message(
            request['message'],
            file_refs
        )

        user_message = {
            'role': 'user',
            'content': user_message_content
        }
        context.append(user_message)

        # Step 6: Set current request context (for tools to access file_refs)
        from app.dependencies import set_current_request
        set_current_request(request)

        # Step 7: Resolve routing using PreferenceResolver (unified preference handling)
        # Both Web UI model selector and Discord /model use the same path via PreferenceResolver
        source = request.get('metadata', {}).get('source', 'discord')

        route_config, resolved_prefs = await self._resolve_route_config(
            request=request,
            user_prefs=user_prefs,
            file_refs=file_refs,
            user_message_content=user_message_content,
            source=source
        )

        logger.info(f"🎯 Route resolved: {route_config['route']} via {resolved_prefs.model_source if resolved_prefs else 'legacy'} [streaming]")

        # Use resolved temperature
        temperature = resolved_prefs.temperature if resolved_prefs else settings.DEFAULT_TEMPERATURE

        # Step 8: Smart router reuse logic (check if we can reuse router for SELF_HANDLE)
        # NOTE: This is only needed when router is a SEPARATE model from execution model
        # In performance profile, router == execution model (gpt-oss:120b), so no special handling needed
        if route_config['route'] == 'SELF_HANDLE' and route_config['model'] == settings.ROUTER_MODEL:
            # Router model will be used for execution - it just stays loaded
            # No need to unload/reload when router == execution model
            logger.debug(f"✅ Reusing {settings.ROUTER_MODEL} for SELF_HANDLE (router == execution model) [streaming]")
        elif route_config['route'] != 'SELF_HANDLE':
            # Different model needed - unload router (conservative mode only)
            if settings.VRAM_CONSERVATIVE_MODE:
                await force_unload_model(settings.ROUTER_MODEL)
                logger.debug(f"🔽 Conservative mode: Unloaded router to load {route_config['model']} [streaming]")
            else:
                profile_name = get_active_profile().profile_name.title()
                logger.debug(f"💤 {profile_name} profile: Router + {route_config['model']} can coexist [streaming]")

        # Step 9: Stream generation
        # NOTE: OCR preprocessing removed - file content already in user_message_content via FileContextBuilder
        accumulated_chunks = []
        first_chunk = True
        status_sent = True  # Status already sent by queue_worker before processing
        MIN_CONTENT_LENGTH = 20  # Minimum characters before replacing status indicator
        generation_start_time = asyncio.get_event_loop().time()  # Track generation timing

        # Use filtered prompt for main LLM if available (clean file language)
        if route_config.get('filtered_prompt'):
            # Replace last message (user message) with filtered version for LLM
            context[-1]['content'] = route_config['filtered_prompt']
            logger.debug(f"🧹 Using filtered prompt for main LLM: {route_config['filtered_prompt'][:80]}...")

        chunk_count = 0
        async for chunk in self.llm.generate_stream_with_route(
            context=context,
            route_config=route_config,
            temperature=temperature,
            user_base_prompt=user_prefs.get('base_prompt'),
            user_thinking_enabled=resolved_prefs.thinking_enabled if resolved_prefs else user_prefs.get('thinking_enabled')
        ):
            chunk_count += 1
            logger.debug(f"🔍 Chunk #{chunk_count}: len={len(chunk)}, stripped_len={len(chunk.strip())}, preview={repr(chunk[:50])}")

            # Skip LLM-generated status indicators (we already sent one from queue_worker)
            # Pattern: *Something...*\n\n (e.g., "*Pondering...*\n\n")
            if status_sent and re.match(r'^\*[^*]+\.\.\.\*\s*$', chunk.strip()):
                logger.debug(f"⏭️  Skipping LLM-generated status indicator: {repr(chunk[:30])}")
                continue  # Don't accumulate or send this chunk

            # First chunk is now just regular content (status sent earlier by queue_worker)
            first_chunk = False

            # Don't skip empty chunks - let them accumulate
            # The MIN_CONTENT_LENGTH check below will handle when to send updates
            accumulated_chunks.append(chunk)
            accumulated_content = ''.join(accumulated_chunks)
            logger.debug(f"📊 Accumulated: {len(accumulated_chunks)} chunks, total_len={len(accumulated_content)}, stripped_len={len(accumulated_content.strip())}")

            # If we sent a status indicator, wait until we have meaningful content
            # before replacing it (prevents fragments like "**" from replacing status)
            if status_sent and len(accumulated_content.strip()) < MIN_CONTENT_LENGTH:
                logger.debug(f"⏳ Waiting for {MIN_CONTENT_LENGTH} chars, have {len(accumulated_content.strip())}")
                continue  # Keep accumulating

            # NEW: Additional validation for first chunk after status indicator
            # Ensure it contains at least one alphanumeric character
            if status_sent:
                has_alphanumeric = bool(re.search(r'[a-zA-Z0-9]', accumulated_content))
                if not has_alphanumeric:
                    logger.debug(f"⏳ Waiting for alphanumeric content, have only whitespace/symbols")
                    continue  # Keep accumulating until we have real content

            # Send update only if we have content
            # Note: Send full accumulated_content (for Discord editing + Web UI delta handling)
            if accumulated_content.strip():
                logger.debug(f"📤 Sending update: {len(accumulated_content)} chars")
                await stream_callback(accumulated_content)
                status_sent = False  # After first real update, send normally

        # Step 9: Finalize accumulated response
        response_content = ''.join(accumulated_chunks)

        # Get references from LLM's last streaming invocation
        references = []
        if hasattr(self.llm, 'last_ref_hook') and self.llm.last_ref_hook:
            references = self.llm.last_ref_hook.references
            logger.debug(f"🔗 Captured {len(references)} references from streaming: {[ref['title'] for ref in references]}")

        # Inject URLs into inline 【】 citations
        if references:
            response_content = inject_reference_urls(response_content, references)
            logger.debug(f"🔗 Injected URLs into {len(references)} inline citations (streaming)")

        # Log generated response
        preview = response_content[:150].replace('\n', ' ').replace('\r', ' ')
        logger.info(f"📤 Generated streaming response for user {request['user_id']}: {preview}{'...' if len(response_content) > 150 else ''}")

        # DEBUG: Measure post-generation operations
        import time
        start_time = time.time()
        logger.info(f"📏 Response size: {len(response_content)} chars ({len(response_content.encode('utf-8'))} bytes)")
        logger.debug(f"⏱️  Starting post-generation operations")

        # Step 10: Save messages to database
        # Generate message_id if not present (Web UI doesn't send it, Discord does for reactions)
        message_id = request.get('message_id') or str(uuid.uuid4())

        await self.conversation_storage.add_message(
            conversation_id=request['conversation_id'],
            message_id=message_id,
            role='user',
            content=request['message'],
            token_count=request['estimated_tokens'],
            user_id=request['user_id'],
            model_used=user_prefs.get('preferred_model') or 'trollama'
        )

        # DEBUG: Measure user message DB write time
        user_msg_time = time.time()
        logger.info(f"⏱️  User message DB write: {user_msg_time - start_time:.2f}s")
        token_count_start = time.time()

        response_tokens = await self.token_tracker.count_tokens(
            response_content
        )

        # Get thinking tokens from LLM (for accurate TPS calculation)
        thinking_tokens = getattr(self.llm, 'last_thinking_tokens', 0)
        total_tokens_generated = response_tokens + thinking_tokens

        # DEBUG: Measure token counting time
        token_count_end = time.time()
        logger.info(f"⏱️  Token counting: {token_count_end - token_count_start:.2f}s ({response_tokens} output + {thinking_tokens} thinking = {total_tokens_generated} total)")

        # Calculate generation time BEFORE saving to database
        generation_time = asyncio.get_event_loop().time() - generation_start_time

        # Calculate accurate TPS including thinking tokens
        tps = total_tokens_generated / generation_time if generation_time > 0 else 0
        logger.info(f"⚡ TPS: {tps:.1f} t/s (total tokens / time)")

        assistant_msg_start = time.time()

        await self.conversation_storage.add_message(
            conversation_id=request['conversation_id'],
            message_id=f"response_{message_id}",
            role='assistant',
            content=response_content,
            token_count=response_tokens,
            user_id=request['user_id'],
            model_used=route_config['model'],
            generation_time=generation_time  # Save tokens/sec calculation
        )

        # DEBUG: Measure assistant message DB write time
        assistant_msg_end = time.time()
        logger.info(f"⏱️  Assistant message DB write: {assistant_msg_end - assistant_msg_start:.2f}s")
        logger.info(f"📊 Total post-generation time: {assistant_msg_end - start_time:.2f}s")

        # Step 11: Force unload main LLM if post-processing needed (VRAM management)
        # DISABLED: Model unloading causes 2+ minute hangs due to Ollama "Stopping..." issue
        # The extraction model will automatically unload the main model when it loads
        # if 'OUTPUT_ARTIFACT' in route_config.get('postprocessing', []):
        #     unload_start = time.time()
        #     await force_unload_model(route_config['model'])
        #     unload_end = time.time()
        #     logger.info(f"⏱️  Model unload time: {unload_end - unload_start:.2f}s")
        #     logger.debug(f"🔽 Unloaded {route_config['model']} before post-processing (VRAM management)")

        logger.debug("⏭️  Skipping explicit model unload - extraction model will handle it")

        # Step 11: Apply postprocessing strategies (same as non-streaming)
        for strategy_name in route_config.get('postprocessing', []):
            if strategy_name == 'OUTPUT_ARTIFACT':
                artifacts_created = request.get('artifacts_created', [])

                if len(artifacts_created) > 0:
                    logger.info(f"✅ {len(artifacts_created)} artifact(s) created via tools - skipping extraction")
                    continue

                extraction_start = time.time()
                logger.info("📦 No artifacts from tools - attempting extraction fallback")

                # Determine extraction model from resolved preferences
                if resolved_prefs:
                    extraction_model = resolved_prefs.artifact_extraction_model
                    logger.info(f"Using profile artifact extraction model: {extraction_model} [streaming]")
                else:
                    # Fallback: get directly from profile (should not happen)
                    extraction_model = get_active_profile().artifact_extraction_model
                    logger.warning(f"⚠️  resolved_prefs is None - falling back to profile: {extraction_model} [streaming]")

                # Create OutputArtifactStrategy with preferred model
                from app.strategies.output_artifact_strategy import OutputArtifactStrategy
                strategy = OutputArtifactStrategy(
                    ollama_host=settings.OLLAMA_HOST,
                    model=extraction_model
                )

                # Execute extraction
                from app.services.file_service import FileService
                context_dict = {
                    'user_message': request['message'],
                    'llm_response': response_content,
                    'file_service': FileService()
                }

                artifacts_from_strategy = await strategy.process(context_dict)
                extraction_end = time.time()
                logger.info(f"⏱️  Artifact extraction time: {extraction_end - extraction_start:.2f}s")

                if len(artifacts_from_strategy) > 0:
                    logger.info(f"✅ Extracted {len(artifacts_from_strategy)} artifact(s) via postprocessing fallback")
                    request['artifacts_created'] = artifacts_from_strategy
                else:
                    logger.warning(
                        f"⚠️  OUTPUT_ARTIFACT detected but no artifacts created (tools or extraction). "
                        f"User: {request['user_id']}, Message: {request['message'][:100]}"
                    )

                continue

            # Execute other postprocessing strategies (if any)
            logger.info(f"📦 Applying {strategy_name} postprocessing")

            from app.services.file_service import FileService
            context_dict = {
                'user_message': request['message'],
                'llm_response': response_content,
                'file_service': FileService()
            }

            artifacts_from_strategy = await self.strategy_registry.execute(
                strategy_name,
                context_dict
            )

            artifacts = request.get('artifacts_created', []) + artifacts_from_strategy
            request['artifacts_created'] = artifacts

        # Step 12: Update token usage
        total_tokens_used = request['estimated_tokens'] + response_tokens
        await self.token_tracker.update_usage(
            request['user_id'],
            total_tokens_used
        )

        # Step 13: Include artifacts in response (non-editing approach)
        artifacts = request.get('artifacts_created', [])
        if artifacts:
            logger.info(f"📦 {len(artifacts)} artifact(s) created during streaming request")
            # Note: Response content NOT edited - user receives full Discord preview + file

        # Step 14: Clean up temporary upload files
        if file_refs:
            from app.dependencies import get_file_service
            file_service = get_file_service()

            for file_ref in file_refs:
                storage_path = file_ref.get('storage_path')
                if storage_path:
                    try:
                        await file_service.delete_file(storage_path)
                        logger.info(f"🗑️  Cleaned up temp file: {file_ref['filename']}")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to clean up temp file {storage_path}: {e}")

        # Step 15: Force unload after SELF_HANDLE execution
        # MOVED TO QUEUE_WORKER: Model unload happens after WebSocket transmission is complete
        # This prevents race condition where model is unloaded while chunks are still queued
        # if route_config['route'] == 'SELF_HANDLE' and route_config['model'] == settings.ROUTER_MODEL:
        #     # Router was reused for execution - now unload it
        #     await force_unload_model(settings.ROUTER_MODEL)
        #     logger.debug("🔽 Unloaded router after SELF_HANDLE execution [streaming]")

        # generation_time already calculated earlier before DB save (line 758)
        # Get thinking tokens for accurate TPS (calculated earlier at line 750-751)
        thinking_tokens = getattr(self.llm, 'last_thinking_tokens', 0)
        total_tokens_generated = response_tokens + thinking_tokens

        return {
            'request_id': request['request_id'],
            'response': response_content,
            'tokens_used': total_tokens_used,
            'generation_time': generation_time,  # seconds
            'output_tokens': response_tokens,  # For display
            'total_tokens_generated': total_tokens_generated,  # For accurate TPS (includes thinking)
            'model': route_config['model'],
            'artifacts': artifacts,
            'route_config': route_config  # NEW: Return for retry reuse
        }

