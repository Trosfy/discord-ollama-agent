"""Dependency injection for services."""
from contextvars import ContextVar
from app.config import settings
from app.implementations.conversation_storage import ConversationStorage
from app.implementations.user_storage import UserStorage
from app.implementations.memory_queue import MemoryQueue
from app.implementations.strands_llm import StrandsLLM
from app.implementations.websocket_manager import WebSocketManager
from app.services.context_manager import ContextManager
from app.services.token_tracker import TokenTracker
from app.services.summarization_service import SummarizationService
from app.services.router_service import RouterService
from app.services.orchestrator import Orchestrator
from app.services.queue_worker import QueueWorker
from app.services.ocr_service import OCRService
from app.services.file_service import FileService


# Singletons
_storage = None
_user_storage = None
_queue = None
_llm = None
_ws_manager = None
_router_service = None
_orchestrator = None
_queue_worker = None
_ocr_service = None
_file_service = None
_strategy_registry = None
_output_artifact_detector = None
_input_artifact_detector = None

# Context variable for current request (used by tools)
_current_request: ContextVar[dict] = ContextVar('current_request', default={})


def get_storage():
    """
    Get conversation storage implementation (singleton).

    Note: ConversationStorage focuses on conversation threads and messages only.
          For user data (preferences, tokens), use get_user_storage() instead.

    Returns:
        ConversationStorage instance (implements IConversationStorage)
    """
    global _storage
    if _storage is None:
        _storage = ConversationStorage()
    return _storage


def get_user_storage():
    """
    Get user preferences storage implementation (singleton).

    Returns:
        UserStorage instance (implements IUserStorage)
    """
    global _user_storage
    if _user_storage is None:
        _user_storage = UserStorage()
    return _user_storage


def get_queue():
    """
    Get queue implementation (singleton).

    Returns:
        MemoryQueue instance
    """
    global _queue
    if _queue is None:
        _queue = MemoryQueue()
    return _queue


def get_llm():
    """
    Get LLM implementation (singleton).

    Returns:
        StrandsLLM instance
    """
    global _llm
    if _llm is None:
        _llm = StrandsLLM()
    return _llm


def get_websocket_manager():
    """
    Get WebSocket manager (singleton).

    Returns:
        WebSocketManager instance
    """
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager


def get_context_manager():
    """
    Get context manager.

    Returns:
        ContextManager instance
    """
    return ContextManager(storage=get_storage())


def get_token_tracker():
    """
    Get token tracker.

    Note: Now uses UserStorage for token tracking (not DynamoDBStorage).

    Returns:
        TokenTracker instance
    """
    return TokenTracker(storage=get_user_storage(), llm=get_llm())


def get_summarization_service():
    """
    Get summarization service.

    Returns:
        SummarizationService instance
    """
    return SummarizationService(storage=get_storage(), llm=get_llm())


def get_router_service():
    """
    Get router service (singleton).

    Returns:
        RouterService instance
    """
    global _router_service
    if _router_service is None:
        _router_service = RouterService(
            output_detector=get_output_artifact_detector(),
            input_detector=get_input_artifact_detector()
        )
    return _router_service


def get_orchestrator():
    """
    Get orchestrator (singleton).

    Returns:
        Orchestrator instance
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator(
            conversation_storage=get_storage(),
            user_storage=get_user_storage(),
            llm=get_llm(),
            context_manager=get_context_manager(),
            token_tracker=get_token_tracker(),
            summarization_service=get_summarization_service(),
            router_service=get_router_service(),
            strategy_registry=get_strategy_registry()
        )
    return _orchestrator


def get_queue_worker():
    """
    Get queue worker (singleton).

    Returns:
        QueueWorker instance
    """
    global _queue_worker
    if _queue_worker is None:
        _queue_worker = QueueWorker(
            queue=get_queue(),
            orchestrator=get_orchestrator(),
            ws_manager=get_websocket_manager()
        )
    return _queue_worker


def get_ocr_service():
    """
    Get OCR service (singleton).

    Returns:
        OCRService instance
    """
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService(
            ollama_host=settings.OLLAMA_HOST
        )
    return _ocr_service


def get_file_service():
    """
    Get file service (singleton).

    Returns:
        FileService instance
    """
    global _file_service
    if _file_service is None:
        _file_service = FileService(
            ocr_service=get_ocr_service()
        )
    return _file_service


def get_current_request() -> dict:
    """
    Get current request context (for tools to access file refs).

    Returns:
        Dict containing current request data (file_refs, etc.)
    """
    return _current_request.get()


def set_current_request(request: dict):
    """
    Set current request context (called by orchestrator before tool execution).

    Args:
        request: Request dict with file_refs and other metadata
    """
    _current_request.set(request)


def get_strategy_registry():
    """Get strategy registry (singleton)."""
    global _strategy_registry
    if _strategy_registry is None:
        from app.services.strategy_registry import StrategyRegistry
        from app.strategies.output_artifact_strategy import OutputArtifactStrategy

        registry = StrategyRegistry()

        # Register strategies
        registry.register(
            'OUTPUT_ARTIFACT',
            OutputArtifactStrategy(
                ollama_host=settings.OLLAMA_HOST,
                model=settings.POST_PROCESSING_OUTPUT_ARTIFACT_MODEL
            )
        )

        _strategy_registry = registry
    return _strategy_registry


def get_output_artifact_detector():
    """Get output artifact detector (singleton)."""
    global _output_artifact_detector
    if _output_artifact_detector is None:
        from app.services.output_artifact_detector import OutputArtifactDetector
        _output_artifact_detector = OutputArtifactDetector(
            ollama_host=settings.OLLAMA_HOST,
            model=settings.ROUTER_MODEL
        )
    return _output_artifact_detector


def get_input_artifact_detector():
    """Get input artifact detector (singleton)."""
    global _input_artifact_detector
    if _input_artifact_detector is None:
        from app.services.input_artifact_detector import InputArtifactDetector
        _input_artifact_detector = InputArtifactDetector()
    return _input_artifact_detector
