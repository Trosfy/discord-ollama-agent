"""Main orchestration service coordinating all business logic."""
import sys
sys.path.insert(0, '/shared')

from typing import Dict
import re

from app.config import settings, get_model_capabilities
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
        strategy_registry  # NEW: Inject registry (DIP)
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
        """
        self.conversation_storage = conversation_storage
        self.user_storage = user_storage
        self.llm = llm
        self.context_manager = context_manager
        self.token_tracker = token_tracker
        self.summarization_service = summarization_service
        self.router_service = router_service
        self.strategy_registry = strategy_registry
        self.file_context_builder = FileContextBuilder()  # SOLID: Extract preprocessing

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
            request: Request dictionary with user_id, thread_id, message, etc.
            route_config: Optional route config to skip routing (for retries)

        Returns:
            Result dictionary with response, tokens_used, model

        Raises:
            Exception: If token budget exceeded or generation fails
        """
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

        # Step 4: Load thread context
        context = await self.context_manager.get_thread_context(
            request['thread_id'],
            request['user_id']
        )

        # Step 5: Check if summarization needed
        total_tokens = sum(msg['token_count'] for msg in context)
        if total_tokens > user_prefs['auto_summarize_threshold']:
            context = await self.summarization_service.summarize_and_prune(
                thread_id=request['thread_id'],
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

        # Step 8: Check for user model preference and optionally skip router
        file_refs = request.get('file_refs', [])
        preferred_model = user_prefs.get('preferred_model')

        if route_config is None:  # NEW: Skip routing if config provided
            if preferred_model:
                # User wants specific model - skip router classification entirely!
                logger.info(f"👤 Using user preferred model {preferred_model}, skipping classification")
                route_config = {
                    'route': 'SELF_HANDLE',  # Treat as direct execution
                    'model': preferred_model,
                    'mode': 'single',
                    'preprocessing': ['INPUT_ARTIFACT'] if len(file_refs) > 0 else [],
                    'postprocessing': []  # Will be determined by output detector if needed
                }
            else:
                # Use router for classification WITH enriched message (includes file content)
                route_config = await self.router_service.classify_request(
                    user_message=user_message_content,
                    file_refs=file_refs
                )
                logger.info(f"🎯 Routed to: {route_config['route']} ({route_config})")
        else:
            logger.info(f"♻️  Reusing route config: {route_config['route']} ({route_config})")

        # Use user's temperature preference, fallback to DEFAULT_TEMPERATURE
        temperature = user_prefs.get('temperature')
        if temperature is None:
            temperature = settings.DEFAULT_TEMPERATURE
        else:
            temperature = float(temperature)

        # Step 9: Smart router reuse logic (check if we can reuse router for SELF_HANDLE)
        if route_config['route'] == 'SELF_HANDLE' and route_config['model'] == settings.ROUTER_MODEL:
            # Check if user has custom settings that differ from router defaults
            user_temp = user_prefs.get('temperature')
            user_thinking = user_prefs.get('thinking_enabled')

            # Router defaults: temp=0.1, thinking=None
            has_custom_temp = (user_temp is not None and user_temp != 0.1)
            has_custom_thinking = (user_thinking is not None)

            if not has_custom_temp and not has_custom_thinking:
                # Perfect match! Reuse router with keep_alive=120s
                logger.debug(f"✅ Reusing router for SELF_HANDLE (all defaults)")
                # Router stays loaded, will be used for execution
            else:
                # User has custom settings - need to reload
                logger.debug(f"🔄 Reloading router with user settings (temp={user_temp}, thinking={user_thinking})")
                await force_unload_model(settings.ROUTER_MODEL)
        elif route_config['route'] != 'SELF_HANDLE':
            # Different model needed - force unload router
            await force_unload_model(settings.ROUTER_MODEL)
            logger.debug(f"🔄 Unloaded router to load {route_config['model']}")

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
            user_thinking_enabled=user_prefs.get('thinking_enabled')
        )

        # Format and append references if present
        response_content = response['content']

        # Validate response is not empty
        if not response_content or not response_content.strip():
            logger.error(f"❌ LLM returned empty response for route {route_config.get('route')} with model {route_config.get('model')}")
            logger.error(f"   User thinking preference: {user_prefs.get('thinking_enabled')}, Temperature: {temperature}")
            raise Exception(f"LLM returned empty response (route: {route_config.get('route')}, model: {route_config.get('model')})")

        references = response.get('references', [])

        # Log generated response (replace newlines for clean single-line log)
        preview = response_content[:150].replace('\n', ' ').replace('\r', ' ')
        logger.info(f"📤 Generated response for user {request['user_id']}: {preview}{'...' if len(response_content) > 150 else ''}")

        if references:
            # Format references section at the END of response
            # This ensures references appear in the LAST chunk when Discord splits message
            ref_lines = ["\n\n---", "**References:**"]
            for i, ref in enumerate(references, 1):
                # Use Discord markdown hyperlink format: [text](url)
                ref_lines.append(f"[{i}] [{ref['title']}]({ref['url']})")

            response_content += '\n'.join(ref_lines)

        # Step 8: Save messages to database
        await self.conversation_storage.add_message(
            thread_id=request['thread_id'],
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
            thread_id=request['thread_id'],
            message_id=f"response_{request['message_id']}",
            role='assistant',
            content=response_content,
            token_count=response_tokens,
            user_id=request['user_id'],
            model_used=response['model']
        )

        # Step 8.5: Force unload main LLM if post-processing needed (VRAM management)
        if 'OUTPUT_ARTIFACT' in route_config.get('postprocessing', []):
            await force_unload_model(response['model'])
            logger.debug(f"🔽 Unloaded {response['model']} before post-processing (VRAM management)")

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
                logger.info("📦 No artifacts from tools - attempting extraction fallback")

                # Determine extraction model: user preference or system default
                extraction_model = settings.POST_PROCESSING_OUTPUT_ARTIFACT_MODEL  # System default: ministral-3:14b
                if preferred_model:
                    extraction_model = preferred_model
                    logger.info(f"👤 Using user's model {extraction_model} for artifact extraction")

                # Create OutputArtifactStrategy with preferred model
                from app.strategies.output_artifact_strategy import OutputArtifactStrategy
                strategy = OutputArtifactStrategy(
                    ollama_host=settings.OLLAMA_HOST,
                    model=extraction_model
                )

                # Execute extraction
                from app.services.file_service import FileService
                context = {
                    'user_message': request['message'],
                    'llm_response': response_content,
                    'file_service': FileService()
                }

                artifacts_from_strategy = await strategy.process(context)

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

        # Step 11: Force unload after SELF_HANDLE execution
        if route_config['route'] == 'SELF_HANDLE' and route_config['model'] == settings.ROUTER_MODEL:
            # Router was reused for execution - now unload it
            await force_unload_model(settings.ROUTER_MODEL)
            logger.debug("🔽 Unloaded router after SELF_HANDLE execution")

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
            request: Request dictionary with user_id, thread_id, message, etc.
            stream_callback: Async callback function to receive chunks

        Returns:
            Result dictionary with final response, tokens_used, model, artifacts

        Raises:
            Exception: If token budget exceeded or generation fails
        """
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

        # Step 3: Load thread context
        context = await self.context_manager.get_thread_context(
            request['thread_id'],
            request['user_id']
        )

        # Step 4: Check if summarization needed
        total_tokens = sum(msg['token_count'] for msg in context)
        if total_tokens > user_prefs['auto_summarize_threshold']:
            context = await self.summarization_service.summarize_and_prune(
                thread_id=request['thread_id'],
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

        # Step 7: Check for user model preference and optionally skip router
        file_refs = request.get('file_refs', [])
        preferred_model = user_prefs.get('preferred_model')

        if preferred_model:
            # User wants specific model - skip router classification entirely!
            logger.info(f"👤 Using user preferred model {preferred_model}, skipping classification [streaming]")
            route_config = {
                'route': 'SELF_HANDLE',  # Treat as direct execution
                'model': preferred_model,
                'mode': 'single',
                'preprocessing': ['INPUT_ARTIFACT'] if len(file_refs) > 0 else [],
                'postprocessing': []  # Will be determined by output detector if needed
            }
        else:
            # Use router for classification WITH enriched message (includes file content)
            route_config = await self.router_service.classify_request(
                user_message=user_message_content,
                file_refs=file_refs
            )
            logger.info(f"🎯 Routed to: {route_config['route']} ({route_config}) [streaming]")

        # Use user's temperature preference, fallback to DEFAULT_TEMPERATURE
        temperature = user_prefs.get('temperature')
        if temperature is None:
            temperature = settings.DEFAULT_TEMPERATURE
        else:
            temperature = float(temperature)

        # Step 8: Smart router reuse logic (check if we can reuse router for SELF_HANDLE)
        if route_config['route'] == 'SELF_HANDLE' and route_config['model'] == settings.ROUTER_MODEL:
            # Check if user has custom settings that differ from router defaults
            user_temp = user_prefs.get('temperature')
            user_thinking = user_prefs.get('thinking_enabled')

            # Router defaults: temp=0.1, thinking=None
            has_custom_temp = (user_temp is not None and user_temp != 0.1)
            has_custom_thinking = (user_thinking is not None)

            if not has_custom_temp and not has_custom_thinking:
                # Perfect match! Reuse router with keep_alive=120s
                logger.debug(f"✅ Reusing router for SELF_HANDLE (all defaults) [streaming]")
                # Router stays loaded, will be used for execution
            else:
                # User has custom settings - need to reload
                logger.debug(f"🔄 Reloading router with user settings (temp={user_temp}, thinking={user_thinking}) [streaming]")
                await force_unload_model(settings.ROUTER_MODEL)
        elif route_config['route'] != 'SELF_HANDLE':
            # Different model needed - force unload router
            await force_unload_model(settings.ROUTER_MODEL)
            logger.debug(f"🔄 Unloaded router to load {route_config['model']} [streaming]")

        # Step 9: Stream generation
        # NOTE: OCR preprocessing removed - file content already in user_message_content via FileContextBuilder
        accumulated_chunks = []
        first_chunk = True
        status_sent = True  # Status already sent by queue_worker before processing
        MIN_CONTENT_LENGTH = 20  # Minimum characters before replacing status indicator

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
            user_thinking_enabled=user_prefs.get('thinking_enabled')
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
            if accumulated_content.strip():
                logger.debug(f"📤 Sending update: {len(accumulated_content)} chars")
                await stream_callback(accumulated_content)
                status_sent = False  # After first real update, send normally

        # Step 9: Finalize accumulated response
        response_content = ''.join(accumulated_chunks)

        # Note: References not captured in streaming mode (ref_hook is per-invocation)
        # This is a known limitation - consider capturing references differently if needed
        references = []

        # Log generated response
        preview = response_content[:150].replace('\n', ' ').replace('\r', ' ')
        logger.info(f"📤 Generated streaming response for user {request['user_id']}: {preview}{'...' if len(response_content) > 150 else ''}")

        # DEBUG: Measure post-generation operations
        import time
        start_time = time.time()
        logger.info(f"📏 Response size: {len(response_content)} chars ({len(response_content.encode('utf-8'))} bytes)")
        logger.debug(f"⏱️  Starting post-generation operations")

        # Step 10: Save messages to database
        await self.conversation_storage.add_message(
            thread_id=request['thread_id'],
            message_id=request['message_id'],
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

        # DEBUG: Measure token counting time
        token_count_end = time.time()
        logger.info(f"⏱️  Token counting: {token_count_end - token_count_start:.2f}s ({response_tokens} tokens)")
        assistant_msg_start = time.time()

        await self.conversation_storage.add_message(
            thread_id=request['thread_id'],
            message_id=f"response_{request['message_id']}",
            role='assistant',
            content=response_content,
            token_count=response_tokens,
            user_id=request['user_id'],
            model_used=route_config['model']
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

                # Determine extraction model: user preference or system default
                extraction_model = settings.POST_PROCESSING_OUTPUT_ARTIFACT_MODEL  # System default: ministral-3:14b
                if preferred_model:
                    extraction_model = preferred_model
                    logger.info(f"👤 Using user's model {extraction_model} for artifact extraction [streaming]")

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

        return {
            'request_id': request['request_id'],
            'response': response_content,
            'tokens_used': total_tokens_used,
            'model': route_config['model'],
            'artifacts': artifacts,
            'route_config': route_config  # NEW: Return for retry reuse
        }

