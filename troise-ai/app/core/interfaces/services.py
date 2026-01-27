"""Service interfaces for dependency inversion."""
from typing import TYPE_CHECKING, Protocol, List, Dict, Any, Optional, Tuple

if TYPE_CHECKING:
    from ..context import ExecutionContext
    from ..executor import ExecutionResult
    from ..router import RoutingResult


class IBrainService(Protocol):
    """Interface for brain/knowledge base operations."""

    async def search(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for relevant notes."""
        ...

    async def fetch(self, path: str) -> Dict[str, Any]:
        """Fetch full note content."""
        ...


class IVaultService(Protocol):
    """Interface for Obsidian vault operations."""

    async def read_yaml(self, path: str) -> Dict[str, Any]:
        """Read YAML file from vault."""
        ...

    async def write_yaml(self, path: str, data: Dict[str, Any]) -> None:
        """Write YAML file to vault."""
        ...

    async def read_note(self, path: str) -> str:
        """Read markdown note content."""
        ...

    async def write_note(self, path: str, content: str) -> None:
        """Write markdown note to vault."""
        ...

    async def list_notes(self, directory: str = None) -> List[str]:
        """List notes in vault or directory."""
        ...


class IUserMemory(Protocol):
    """Interface for user memory/preferences storage."""

    async def get_all(self, user_id: str) -> List[Dict]:
        """Get all memory items for a user."""
        ...

    async def get(
        self,
        user_id: str,
        category: str,
        key: str
    ) -> Optional[Dict]:
        """Get specific memory item."""
        ...

    async def query(
        self,
        user_id: str,
        category: str = None
    ) -> List[Dict]:
        """Query memory by category."""
        ...

    async def put(
        self,
        user_id: str,
        category: str,
        key: str,
        value: str,
        source: str = "learned",
        confidence: float = 1.0,
        learned_by: str = None,
        ttl: int = None
    ) -> None:
        """Store a memory item."""
        ...

    async def delete(
        self,
        user_id: str,
        category: str,
        key: str
    ) -> None:
        """Delete a memory item."""
        ...


class IEmbeddingService(Protocol):
    """Interface for text embeddings."""

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        ...

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        ...


class IVRAMOrchestrator(Protocol):
    """Interface for VRAM and model management.

    Provides the primary interface for getting models.
    Handles VRAM management, model loading, and returns Strands-compatible Models.

    Example:
        orchestrator = container.resolve(IVRAMOrchestrator)

        # Router (no thinking)
        model = await orchestrator.get_model("gpt-oss:20b", additional_args=None)

        # Agent (with thinking)
        model = await orchestrator.get_model("magistral:24b", additional_args={"think": "high"})
        agent = Agent(model=model, tools=[...])
    """

    async def get_model(
        self,
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        additional_args: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Get a Strands-compatible Model for the specified model.

        Ensures the model is loaded in VRAM and returns a configured model.
        Returns OllamaModel or OpenAIModel based on backend type.

        Args:
            model_id: The model identifier (e.g., "magistral:24b").
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            additional_args: Optional backend-specific options.
                For Ollama: {"think": "high"} enables thinking, None disables.
                For OpenAI-compatible: merged into params.
                If not provided, auto-resolves from model capabilities.

        Returns:
            Strands Model instance (OllamaModel or OpenAIModel).
        """
        ...

    async def request_load(self, model_id: str) -> bool:
        """Request to load a model. Handles eviction if needed.

        Args:
            model_id: The model identifier to load.

        Returns:
            True if the model was loaded successfully.
        """
        ...

    def is_loaded(self, model_id: str) -> bool:
        """Check if a model is currently loaded.

        Args:
            model_id: The model identifier to check.

        Returns:
            True if the model is loaded.
        """
        ...

    def get_profile_model(self, role: str = "agent") -> str:
        """Get the default model for a role from the current profile.

        Args:
            role: Model role - "agent", "router", "code", "vision", "embedding"

        Returns:
            Model ID from the profile for the specified role.
        """
        ...

    def get_model_capabilities(self, model_id: str) -> Optional[Any]:
        """Get capabilities for a model if it exists in the current profile.

        Used for validation when user specifies a model via user_config.
        Returns ModelCapabilities if found, None otherwise.

        Args:
            model_id: The model identifier to look up.

        Returns:
            ModelCapabilities if found, None otherwise.
        """
        ...

    async def list_available_models(self) -> List[Dict[str, Any]]:
        """List all models available in the current profile with their capabilities.

        Used by /models endpoint for web-service dropdown population.

        Returns:
            List of model info dicts including name, capabilities, and settings.
        """
        ...

    async def get_diffusion_pipeline(self, model_id: str) -> Any:
        """Get a diffusion pipeline for image generation.

        Ensures the model is loaded in VRAM and returns the pipeline.
        Only works for models with model_type="diffusion".

        Args:
            model_id: The diffusion model identifier (e.g., "flux2-dev-bnb4bit").

        Returns:
            Diffusion pipeline (e.g., Flux2Pipeline).

        Raises:
            ValueError: If model is not in profile or not a diffusion model.
            MemoryError: If there's not enough VRAM and eviction failed.
            RuntimeError: If diffusion backend is not available.
        """
        ...

    def get_diffusion_client(self, model_id: str) -> Any:
        """Get ComfyUI client for diffusion model image generation.

        Used for NVFP4 models that run via ComfyUI backend instead of
        in-process diffusers. Returns the ComfyUIClient for direct HTTP
        communication with the ComfyUI server.

        Args:
            model_id: Diffusion model identifier (e.g., "flux2-dev-nvfp4").

        Returns:
            ComfyUIClient instance for image generation.

        Raises:
            ValueError: If model not in profile or not a diffusion model.
            RuntimeError: If ComfyUI backend not configured.
        """
        ...

    async def get_diffusion_context(self, model_id: str) -> Tuple[Any, Dict[str, Any]]:
        """Get ComfyUI client and workflow config for diffusion model.

        Ensures VRAM is available by calling request_load(), which may evict
        LLMs if needed. The diffusion model is registered in the registry
        for future eviction when LLMs need to load.

        Returns both the client and the model-specific workflow configuration
        from ModelCapabilities.options. This follows DIP by keeping model
        configuration in the profile rather than hardcoded in the client.

        Args:
            model_id: Diffusion model identifier (e.g., "flux2-dev-nvfp4").

        Returns:
            Tuple of (ComfyUIClient, workflow_config dict).

        Raises:
            ValueError: If model not in profile or not a diffusion model.
            RuntimeError: If ComfyUI backend not configured.
            MemoryError: If there's not enough VRAM and eviction failed.
        """
        ...

    async def warmup_diffusion_model(self, model_id: Optional[str] = None) -> bool:
        """Pre-load diffusion model into VRAM by triggering a warmup workflow.

        ComfyUI models load lazily on first workflow submission. This method
        submits a tiny 64x64 image to trigger model loading before user requests.

        Args:
            model_id: Diffusion model ID. If None, uses profile's default image model.

        Returns:
            True if warmup succeeded, False otherwise.
        """
        ...


class IComfyUICompletionWaiter(Protocol):
    """Protocol for ComfyUI workflow completion detection.

    Follows ISP - only defines the wait behavior, not connection management.
    Implementations can use WebSocket, polling, or other mechanisms.
    """

    async def wait_for_completion(
        self,
        prompt_id: str,
        timeout_seconds: float = 900
    ) -> bool:
        """Wait for a ComfyUI prompt to complete.

        Args:
            prompt_id: The ComfyUI prompt ID to wait for.
            timeout_seconds: Maximum time to wait.

        Returns:
            True if completed successfully, False on error/timeout.
        """
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the waiter is ready to receive events."""
        ...


class IExecutor(Protocol):
    """Interface for skill/agent execution.

    Abstracts the Executor so queue workers can depend on the interface
    rather than the concrete implementation (Dependency Inversion Principle).

    Example:
        executor = container.resolve(IExecutor)
        result = await executor.execute(routing_result, user_input, context)
    """

    async def execute(
        self,
        routing_result: "RoutingResult",
        user_input: str,
        context: "ExecutionContext",
    ) -> "ExecutionResult":
        """Execute a skill or agent based on routing result.

        Args:
            routing_result: Result from Router indicating which plugin to use.
            user_input: The original user input.
            context: Execution context with user info, interface, etc.

        Returns:
            ExecutionResult with content and metadata.

        Raises:
            PluginNotFoundError: If the plugin is not in registry.
            PluginError: If plugin execution fails.
        """
        ...


# =============================================================================
# RAG (Retrieval-Augmented Generation) Interfaces
# =============================================================================

from pydantic import BaseModel


class TextChunk(BaseModel):
    """Represents a chunk of text with metadata for RAG operations."""
    chunk_id: str  # UUID
    text: str  # The actual chunk text
    chunk_index: int  # Position in original document (0-based)
    token_count: int  # Number of tokens in this chunk
    source_url: str  # Original source URL
    start_char: int  # Starting character position in original text
    end_char: int  # Ending character position in original text


class WebChunk(BaseModel):
    """Represents a stored web chunk with embedding vector."""
    chunk_id: str  # UUID
    chunk_text: str  # The actual text content
    embedding_vector: List[float]  # Embedding vector
    chunk_index: int  # Position in original document (0-based)
    token_count: int  # Number of tokens in chunk
    source_url: str  # Original source URL
    start_char: int  # Starting character position
    end_char: int  # Ending character position
    created_at: str  # ISO timestamp
    url_hash: str  # SHA256 hash of URL (partition key)


class IChunkingService(Protocol):
    """Interface for text chunking services.

    Splits text into overlapping chunks with consistent token counts.
    Follows Interface Segregation Principle - focused on chunking only.
    """

    async def chunk_text(
        self,
        text: str,
        source_url: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> List[TextChunk]:
        """Split text into overlapping chunks with metadata.

        Args:
            text: The text content to chunk
            source_url: Source URL for attribution
            chunk_size: Target tokens per chunk
            chunk_overlap: Token overlap between consecutive chunks

        Returns:
            List of TextChunk objects with IDs, indices, and metadata

        Raises:
            ValueError: If text is empty or parameters are invalid
        """
        ...


class IVectorStorage(Protocol):
    """Interface for web chunk vector storage operations.

    Provides cache-based storage for web page chunks with embeddings.
    Supports domain-specific TTLs and similarity search.
    """

    async def store_chunks(
        self,
        url: str,
        chunks: List[Dict[str, Any]],
        ttl_hours: Optional[int] = None
    ) -> int:
        """Store webpage chunks with embeddings and TTL.

        Args:
            url: Source URL (will be hashed for partition key)
            chunks: List of dicts with keys: chunk_id, chunk_text, embedding_vector,
                   chunk_index, token_count, start_char, end_char
            ttl_hours: Override TTL in hours (uses domain/default if None)

        Returns:
            Number of chunks stored

        Raises:
            ValueError: If url or chunks are invalid
        """
        ...

    async def get_chunks_by_url(self, url: str) -> Optional[List[WebChunk]]:
        """Retrieve all chunks for a URL (cache check).

        Args:
            url: Source URL to look up

        Returns:
            List of WebChunk objects if found and not expired, None otherwise
        """
        ...

    async def is_cached(self, url: str) -> bool:
        """Quick check if URL is in cache and not expired.

        Args:
            url: URL to check

        Returns:
            True if cached and valid
        """
        ...

    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[WebChunk]:
        """Search for most similar chunks using cosine similarity.

        Args:
            query_embedding: Query vector to compare against
            top_k: Number of top results to return

        Returns:
            List of WebChunk objects sorted by similarity (highest first)

        Note:
            Uses client-side cosine similarity computation.
            For production scale, consider Pinecone/Weaviate/pgvector.
        """
        ...

    async def delete_url(self, url: str) -> int:
        """Force delete URL and all its chunks.

        Args:
            url: URL to delete

        Returns:
            Number of items deleted
        """
        ...
