"""Dependency injection for services."""
from app.config import settings
from app.implementations.dynamodb_storage import DynamoDBStorage
from app.implementations.memory_queue import MemoryQueue
from app.implementations.strands_llm import StrandsLLM
from app.implementations.websocket_manager import WebSocketManager
from app.services.context_manager import ContextManager
from app.services.token_tracker import TokenTracker
from app.services.summarization_service import SummarizationService
from app.services.router_service import RouterService
from app.services.orchestrator import Orchestrator
from app.services.queue_worker import QueueWorker


# Singletons
_storage = None
_queue = None
_llm = None
_ws_manager = None
_router_service = None
_orchestrator = None
_queue_worker = None


def get_storage():
    """
    Get storage implementation (singleton).

    Returns:
        DynamoDBStorage instance
    """
    global _storage
    if _storage is None:
        _storage = DynamoDBStorage()
    return _storage


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

    Returns:
        TokenTracker instance
    """
    return TokenTracker(storage=get_storage(), llm=get_llm())


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
        _router_service = RouterService()
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
            storage=get_storage(),
            llm=get_llm(),
            context_manager=get_context_manager(),
            token_tracker=get_token_tracker(),
            summarization_service=get_summarization_service(),
            router_service=get_router_service()
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
