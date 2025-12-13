"""Main orchestration service coordinating all business logic."""
import sys
sys.path.insert(0, '/shared')

from typing import Dict

from app.interfaces.storage import StorageInterface
from app.interfaces.llm import LLMInterface
from app.services.context_manager import ContextManager
from app.services.token_tracker import TokenTracker
from app.services.summarization_service import SummarizationService
from app.services.router_service import RouterService
from app.utils.message_classifier import is_simple_greeting, get_greeting_response
from app.config import settings
import logging_client

# Initialize logger
logger = logging_client.setup_logger('fastapi')


class Orchestrator:
    """Coordinates all services without containing business logic (SOLID)."""

    def __init__(
        self,
        storage: StorageInterface,
        llm: LLMInterface,
        context_manager: ContextManager,
        token_tracker: TokenTracker,
        summarization_service: SummarizationService,
        router_service: RouterService
    ):
        """
        Initialize orchestrator with all required services.

        Args:
            storage: Storage interface for persistence
            llm: LLM interface for generation
            context_manager: Context retrieval service
            token_tracker: Token management service
            summarization_service: Summarization service
            router_service: Router service for request classification
        """
        self.storage = storage
        self.llm = llm
        self.context_manager = context_manager
        self.token_tracker = token_tracker
        self.summarization_service = summarization_service
        self.router_service = router_service

    async def process_request(self, request: Dict) -> Dict:
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

        Returns:
            Result dictionary with response, tokens_used, model

        Raises:
            Exception: If token budget exceeded or generation fails
        """
        # Log incoming request
        logger.info(f"📥 Processing request from user {request['user_id']}: {request['message']}")

        # Step 1: Check for simple greetings (save LLM costs)
        if is_simple_greeting(request['message']):
            logger.info(f"👋 Detected simple greeting from user {request['user_id']}")
            greeting_response = get_greeting_response()

            # Save greeting exchange to database
            await self.storage.add_message(
                thread_id=request['thread_id'],
                message_id=request['message_id'],
                role='user',
                content=request['message'],
                token_count=request['estimated_tokens'],
                user_id=request['user_id'],
                model_used='none'
            )

            response_tokens = await self.token_tracker.count_tokens(greeting_response)

            await self.storage.add_message(
                thread_id=request['thread_id'],
                message_id=f"response_{request['message_id']}",
                role='assistant',
                content=greeting_response,
                token_count=response_tokens,
                user_id=request['user_id'],
                model_used='none'
            )

            return {
                'request_id': request['request_id'],
                'response': greeting_response,
                'tokens_used': 0,  # No LLM tokens used
                'model': 'greeting_handler'
            }

        # Step 2: Get user
        user = await self.storage.get_user(request['user_id'])
        if not user:
            # Create new user
            await self.storage.create_user(
                user_id=request['user_id'],
                discord_username=f"user_{request['user_id'][:8]}",
                user_tier='free'
            )
            user = await self.storage.get_user(request['user_id'])

        # Step 3: Check token budget
        if not await self.token_tracker.has_budget(
            user,
            request['estimated_tokens']
        ):
            raise Exception(
                f"Token budget exceeded. Remaining: {user['tokens_remaining']}"
            )

        # Step 4: Load thread context
        context = await self.context_manager.get_thread_context(
            request['thread_id'],
            request['user_id']
        )

        # Step 5: Check if summarization needed
        total_tokens = sum(msg['token_count'] for msg in context)
        if total_tokens > user['auto_summarize_threshold']:
            context = await self.summarization_service.summarize_and_prune(
                thread_id=request['thread_id'],
                messages=context,
                user_id=request['user_id']
            )

        # Step 6: Add user message to context
        user_message = {
            'role': 'user',
            'content': request['message']
        }
        context.append(user_message)

        # Step 7: Classify request using router and generate response
        route = await self.router_service.classify_request(request['message'])
        route_config = self.router_service.get_model_for_route(route)
        logger.info(f"🎯 Routed to: {route.value} ({route_config})")

        response = await self.llm.generate_with_route(
            context=context,
            route_config=route_config,
            temperature=float(user.get('temperature', 0.7)),
            user_base_prompt=user.get('base_prompt')
        )

        # Format and append references if present
        response_content = response['content']
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
        await self.storage.add_message(
            thread_id=request['thread_id'],
            message_id=request['message_id'],
            role='user',
            content=request['message'],
            token_count=request['estimated_tokens'],
            user_id=request['user_id'],
            model_used=user['preferred_model']
        )

        response_tokens = await self.token_tracker.count_tokens(
            response_content
        )

        await self.storage.add_message(
            thread_id=request['thread_id'],
            message_id=f"response_{request['message_id']}",
            role='assistant',
            content=response_content,
            token_count=response_tokens,
            user_id=request['user_id'],
            model_used=response['model']
        )

        # Step 9: Update token usage
        total_tokens_used = request['estimated_tokens'] + response_tokens
        await self.token_tracker.update_usage(
            request['user_id'],
            total_tokens_used
        )

        return {
            'request_id': request['request_id'],
            'response': response_content,
            'tokens_used': total_tokens_used,
            'model': response['model']
        }
