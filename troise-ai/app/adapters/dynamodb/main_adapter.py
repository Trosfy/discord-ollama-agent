"""DynamoDB adapter for troise_main table.

Handles sessions, messages, inferences, and ephemeral memory storage.

Table Design (Single-Table):
    PK patterns:
    - USER#{user_id} - User-scoped data
    - SESSION#{session_id} - Session-scoped data

    SK patterns:
    - META - Metadata for the entity
    - SESSION#{session_id}#{created_at} - Session under user
    - MSG#{timestamp}#{msg_id} - Message in session
    - INFER#{timestamp}#{infer_id} - Inference in session
    - TMP#{key} - Temporary data with TTL
    - MEMORY#{category}#{key} - Learned memory items
"""
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Key, Attr

from .base import DynamoDBClient

logger = logging.getLogger(__name__)

TABLE_NAME = "troise_main"

# TTL durations
TTL_TMP_SECONDS = 3600  # 1 hour for temporary data
TTL_MEMORY_SECONDS = 86400 * 30  # 30 days for memory items
TTL_CHAT_SECONDS = 86400 * 7  # 7 days for chat sessions and messages


@dataclass
class SessionItem:
    """Session metadata item."""
    session_id: str
    user_id: str
    created_at: str  # ISO8601
    updated_at: str  # ISO8601
    interface: str  # discord, web, telegram, etc.
    title: Optional[str] = None
    agent_name: Optional[str] = None
    message_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    ttl: Optional[int] = None  # Unix timestamp for DynamoDB TTL

    @property
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        return f"SESSION#{self.session_id}#{self.created_at}"

    def to_dynamo_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': self.pk,
            'SK': self.sk,
            'entity_type': 'SESSION',
            'session_id': self.session_id,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'interface': self.interface,
            'title': self.title,
            'agent_name': self.agent_name,
            'message_count': self.message_count,
            'metadata': self.metadata,
        }
        if self.ttl:
            item['ttl'] = self.ttl
        return item

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "SessionItem":
        """Create from DynamoDB item."""
        return cls(
            session_id=item['session_id'],
            user_id=item['user_id'],
            created_at=item['created_at'],
            updated_at=item['updated_at'],
            interface=item.get('interface', 'unknown'),
            title=item.get('title'),
            agent_name=item.get('agent_name'),
            message_count=item.get('message_count', 0),
            metadata=item.get('metadata', {}),
            ttl=item.get('ttl'),
        )


@dataclass
class MessageItem:
    """Message item within a session."""
    session_id: str
    msg_id: str
    timestamp: str  # ISO8601
    role: str  # user, assistant, system, tool
    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    ttl: Optional[int] = None  # Unix timestamp for DynamoDB TTL

    @property
    def pk(self) -> str:
        return f"SESSION#{self.session_id}"

    @property
    def sk(self) -> str:
        return f"MSG#{self.timestamp}#{self.msg_id}"

    def to_dynamo_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': self.pk,
            'SK': self.sk,
            'entity_type': 'MSG',
            'session_id': self.session_id,
            'msg_id': self.msg_id,
            'timestamp': self.timestamp,
            'role': self.role,
            'content': self.content,
            'tool_calls': self.tool_calls,
            'tool_results': self.tool_results,
            'metadata': self.metadata,
        }
        if self.ttl:
            item['ttl'] = self.ttl
        return item

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "MessageItem":
        """Create from DynamoDB item."""
        return cls(
            session_id=item['session_id'],
            msg_id=item['msg_id'],
            timestamp=item['timestamp'],
            role=item['role'],
            content=item.get('content', ''),
            tool_calls=item.get('tool_calls', []),
            tool_results=item.get('tool_results', []),
            metadata=item.get('metadata', {}),
            ttl=item.get('ttl'),
        )


@dataclass
class InferenceItem:
    """Inference record for tracking LLM calls."""
    session_id: str
    infer_id: str
    timestamp: str  # ISO8601
    model: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    skill_or_agent: Optional[str] = None
    tool_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    ttl: Optional[int] = None  # Unix timestamp for DynamoDB TTL

    @property
    def pk(self) -> str:
        return f"SESSION#{self.session_id}"

    @property
    def sk(self) -> str:
        return f"INFER#{self.timestamp}#{self.infer_id}"

    def to_dynamo_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            'PK': self.pk,
            'SK': self.sk,
            'entity_type': 'INFER',
            'session_id': self.session_id,
            'infer_id': self.infer_id,
            'timestamp': self.timestamp,
            'model': self.model,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'duration_ms': self.duration_ms,
            'skill_or_agent': self.skill_or_agent,
            'tool_name': self.tool_name,
            'metadata': self.metadata,
        }
        if self.ttl:
            item['ttl'] = self.ttl
        return item

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "InferenceItem":
        """Create from DynamoDB item."""
        return cls(
            session_id=item['session_id'],
            infer_id=item['infer_id'],
            timestamp=item['timestamp'],
            model=item['model'],
            prompt_tokens=item.get('prompt_tokens', 0),
            completion_tokens=item.get('completion_tokens', 0),
            duration_ms=item.get('duration_ms', 0),
            skill_or_agent=item.get('skill_or_agent'),
            tool_name=item.get('tool_name'),
            metadata=item.get('metadata', {}),
            ttl=item.get('ttl'),
        )


@dataclass
class MemoryItem:
    """Learned memory item for user context.

    Memory items are ephemeral learned context that can be promoted
    to ai-learned.yaml when confidence reaches threshold.
    """
    user_id: str
    category: str  # expertise, preference, project, fact
    key: str  # unique identifier within category
    value: str  # the learned content
    confidence: float = 0.5  # 0.0-1.0, promotes to file at 0.9+
    source: str = "learned"  # learned, observed, stated
    learned_by: Optional[str] = None  # agent that learned this
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    evidence: Optional[str] = None  # why we believe this
    ttl: Optional[int] = None  # Unix timestamp for expiry

    @property
    def pk(self) -> str:
        return f"USER#{self.user_id}"

    @property
    def sk(self) -> str:
        return f"MEMORY#{self.category}#{self.key}"

    def to_dynamo_item(self) -> Dict[str, Any]:
        """Convert to DynamoDB item format."""
        now = datetime.now().isoformat()
        item = {
            'PK': self.pk,
            'SK': self.sk,
            'entity_type': 'MEMORY',
            'user_id': self.user_id,
            'category': self.category,
            'key': self.key,
            'value': self.value,
            'confidence': str(self.confidence),  # DynamoDB doesn't have float
            'source': self.source,
            'learned_by': self.learned_by,
            'created_at': self.created_at or now,
            'updated_at': now,
            'evidence': self.evidence,
        }
        if self.ttl:
            item['ttl'] = self.ttl
        return item

    @classmethod
    def from_dynamo_item(cls, item: Dict[str, Any]) -> "MemoryItem":
        """Create from DynamoDB item."""
        return cls(
            user_id=item['user_id'],
            category=item['category'],
            key=item['key'],
            value=item['value'],
            confidence=float(item.get('confidence', '0.5')),
            source=item.get('source', 'learned'),
            learned_by=item.get('learned_by'),
            created_at=item.get('created_at'),
            updated_at=item.get('updated_at'),
            evidence=item.get('evidence'),
            ttl=item.get('ttl'),
        )


class TroiseMainAdapter:
    """
    Adapter for the troise_main DynamoDB table.

    Provides methods for managing sessions, messages, inferences,
    and ephemeral user memory.

    Example:
        client = DynamoDBClient()
        adapter = TroiseMainAdapter(client)

        # Create a session
        session = await adapter.create_session(
            user_id="user123",
            interface="discord"
        )

        # Add a message
        await adapter.add_message(
            session_id=session.session_id,
            role="user",
            content="Hello!"
        )

        # Store a memory
        await adapter.put_memory(
            user_id="user123",
            category="expertise",
            key="python",
            value="Expert Python developer",
            confidence=0.7
        )
    """

    def __init__(self, client: DynamoDBClient):
        """
        Initialize the adapter.

        Args:
            client: DynamoDBClient instance.
        """
        self._client = client
        self._table_name = TABLE_NAME

    # ========== Session Operations ==========

    async def create_session(
        self,
        user_id: str,
        interface: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionItem:
        """
        Create a new session.

        Args:
            user_id: User identifier.
            interface: Interface type (discord, web, etc.).
            title: Optional session title.
            metadata: Optional metadata dict.

        Returns:
            Created SessionItem.
        """
        now = datetime.now().isoformat()
        session = SessionItem(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            created_at=now,
            updated_at=now,
            interface=interface,
            title=title,
            metadata=metadata or {},
            ttl=int(time.time()) + TTL_CHAT_SECONDS,
        )

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.put_item(Item=session.to_dynamo_item())

        logger.info(f"Created session {session.session_id} for user {user_id}")
        return session

    async def get_session(self, user_id: str, session_id: str) -> Optional[SessionItem]:
        """
        Get a session by ID.

        Args:
            user_id: User identifier.
            session_id: Session identifier.

        Returns:
            SessionItem or None if not found.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # Query with begins_with since SK includes created_at
            response = await table.query(
                KeyConditionExpression=Key('PK').eq(f"USER#{user_id}") &
                                       Key('SK').begins_with(f"SESSION#{session_id}#"),
                Limit=1,
            )

            items = response.get('Items', [])
            if items:
                return SessionItem.from_dynamo_item(items[0])
            return None

    async def list_sessions(
        self,
        user_id: str,
        limit: int = 20,
        oldest_first: bool = False,
    ) -> List[SessionItem]:
        """
        List sessions for a user.

        Args:
            user_id: User identifier.
            limit: Maximum number of sessions to return.
            oldest_first: If True, return oldest first. Default is newest first.

        Returns:
            List of SessionItem objects.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            response = await table.query(
                KeyConditionExpression=Key('PK').eq(f"USER#{user_id}") &
                                       Key('SK').begins_with("SESSION#"),
                ScanIndexForward=oldest_first,
                Limit=limit,
            )

            return [SessionItem.from_dynamo_item(item) for item in response.get('Items', [])]

    async def update_session(
        self,
        session: SessionItem,
        title: Optional[str] = None,
        agent_name: Optional[str] = None,
        increment_messages: bool = False,
    ) -> SessionItem:
        """
        Update a session.

        Args:
            session: Session to update.
            title: New title (if provided).
            agent_name: New agent name (if provided).
            increment_messages: If True, increment message_count.

        Returns:
            Updated SessionItem.
        """
        update_expr_parts = ["#updated_at = :updated_at"]
        expr_names = {"#updated_at": "updated_at"}
        expr_values = {":updated_at": datetime.now().isoformat()}

        if title is not None:
            update_expr_parts.append("#title = :title")
            expr_names["#title"] = "title"
            expr_values[":title"] = title
            session.title = title

        if agent_name is not None:
            update_expr_parts.append("#agent_name = :agent_name")
            expr_names["#agent_name"] = "agent_name"
            expr_values[":agent_name"] = agent_name
            session.agent_name = agent_name

        if increment_messages:
            update_expr_parts.append("#message_count = #message_count + :one")
            expr_names["#message_count"] = "message_count"
            expr_values[":one"] = 1
            session.message_count += 1

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.update_item(
                Key={'PK': session.pk, 'SK': session.sk},
                UpdateExpression="SET " + ", ".join(update_expr_parts),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values,
            )

        session.updated_at = expr_values[":updated_at"]
        return session

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """
        Delete a session and all its messages/inferences.

        Args:
            user_id: User identifier.
            session_id: Session identifier.

        Returns:
            True if deleted, False if not found.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            # First, delete all items in the session
            session_pk = f"SESSION#{session_id}"
            response = await table.query(
                KeyConditionExpression=Key('PK').eq(session_pk),
            )

            # Batch delete session items
            for item in response.get('Items', []):
                await table.delete_item(
                    Key={'PK': item['PK'], 'SK': item['SK']}
                )

            # Delete the session metadata from user's sessions
            user_pk = f"USER#{user_id}"
            sessions = await table.query(
                KeyConditionExpression=Key('PK').eq(user_pk) &
                                       Key('SK').begins_with(f"SESSION#{session_id}#"),
            )

            for item in sessions.get('Items', []):
                await table.delete_item(
                    Key={'PK': item['PK'], 'SK': item['SK']}
                )
                logger.info(f"Deleted session {session_id}")
                return True

            return False

    # ========== Message Operations ==========

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MessageItem:
        """
        Add a message to a session.

        Args:
            session_id: Session identifier.
            role: Message role (user, assistant, system, tool).
            content: Message content.
            tool_calls: Optional list of tool calls.
            tool_results: Optional list of tool results.
            metadata: Optional metadata dict.

        Returns:
            Created MessageItem.
        """
        now = datetime.now().isoformat()
        message = MessageItem(
            session_id=session_id,
            msg_id=str(uuid.uuid4()),
            timestamp=now,
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            tool_results=tool_results or [],
            metadata=metadata or {},
            ttl=int(time.time()) + TTL_CHAT_SECONDS,
        )

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.put_item(Item=message.to_dynamo_item())

        logger.debug(f"Added message {message.msg_id} to session {session_id}")
        return message

    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        after_timestamp: Optional[str] = None,
    ) -> List[MessageItem]:
        """
        Get messages from a session.

        Args:
            session_id: Session identifier.
            limit: Maximum number of messages.
            after_timestamp: Only get messages after this timestamp.

        Returns:
            List of MessageItem objects in chronological order.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            key_condition = Key('PK').eq(f"SESSION#{session_id}")

            if after_timestamp:
                key_condition = key_condition & Key('SK').gt(f"MSG#{after_timestamp}")
            else:
                key_condition = key_condition & Key('SK').begins_with("MSG#")

            response = await table.query(
                KeyConditionExpression=key_condition,
                ScanIndexForward=True,  # Chronological order
                Limit=limit,
            )

            return [MessageItem.from_dynamo_item(item) for item in response.get('Items', [])]

    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 20,
    ) -> List[Dict[str, str]]:
        """
        Get conversation history in LLM message format.

        Args:
            session_id: Session identifier.
            limit: Maximum number of messages.

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """
        messages = await self.get_messages(session_id, limit=limit)
        return [{"role": m.role, "content": m.content} for m in messages]

    # ========== Inference Operations ==========

    async def record_inference(
        self,
        session_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        skill_or_agent: Optional[str] = None,
        tool_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> InferenceItem:
        """
        Record an inference (LLM call) for tracking.

        Args:
            session_id: Session identifier.
            model: Model name used.
            prompt_tokens: Number of prompt tokens.
            completion_tokens: Number of completion tokens.
            duration_ms: Inference duration in milliseconds.
            skill_or_agent: Name of skill or agent that made the call.
            tool_name: Name of tool if this was a tool call.
            metadata: Optional metadata dict.

        Returns:
            Created InferenceItem.
        """
        now = datetime.now().isoformat()
        inference = InferenceItem(
            session_id=session_id,
            infer_id=str(uuid.uuid4()),
            timestamp=now,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
            skill_or_agent=skill_or_agent,
            tool_name=tool_name,
            metadata=metadata or {},
            ttl=int(time.time()) + TTL_CHAT_SECONDS,
        )

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.put_item(Item=inference.to_dynamo_item())

        logger.debug(f"Recorded inference {inference.infer_id}")
        return inference

    async def get_session_inferences(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[InferenceItem]:
        """
        Get all inferences for a session.

        Args:
            session_id: Session identifier.
            limit: Maximum number of inferences.

        Returns:
            List of InferenceItem objects.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            response = await table.query(
                KeyConditionExpression=Key('PK').eq(f"SESSION#{session_id}") &
                                       Key('SK').begins_with("INFER#"),
                ScanIndexForward=True,
                Limit=limit,
            )

            return [InferenceItem.from_dynamo_item(item) for item in response.get('Items', [])]

    # ========== Memory Operations ==========

    async def put_memory(
        self,
        user_id: str,
        category: str,
        key: str,
        value: str,
        confidence: float = 0.5,
        source: str = "learned",
        learned_by: Optional[str] = None,
        evidence: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> MemoryItem:
        """
        Store or update a memory item.

        Args:
            user_id: User identifier.
            category: Memory category (expertise, preference, etc.).
            key: Unique key within category.
            value: The memory content.
            confidence: Confidence level (0.0-1.0).
            source: Source type (learned, observed, stated).
            learned_by: Agent that learned this.
            evidence: Evidence for the memory.
            ttl_seconds: Time-to-live in seconds (optional).

        Returns:
            Created/updated MemoryItem.
        """
        # Check for existing memory to preserve created_at
        existing = await self.get_memory(user_id, category, key)

        ttl = None
        if ttl_seconds:
            ttl = int(time.time()) + ttl_seconds

        memory = MemoryItem(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            source=source,
            learned_by=learned_by,
            created_at=existing.created_at if existing else None,
            evidence=evidence,
            ttl=ttl,
        )

        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)
            await table.put_item(Item=memory.to_dynamo_item())

        logger.debug(f"Put memory {category}/{key} for user {user_id}")
        return memory

    async def get_memory(
        self,
        user_id: str,
        category: str,
        key: str,
    ) -> Optional[MemoryItem]:
        """
        Get a specific memory item.

        Args:
            user_id: User identifier.
            category: Memory category.
            key: Memory key.

        Returns:
            MemoryItem or None if not found.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            response = await table.get_item(
                Key={
                    'PK': f"USER#{user_id}",
                    'SK': f"MEMORY#{category}#{key}",
                }
            )

            item = response.get('Item')
            if item:
                return MemoryItem.from_dynamo_item(item)
            return None

    async def query_memories(
        self,
        user_id: str,
        category: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[MemoryItem]:
        """
        Query memory items for a user.

        Args:
            user_id: User identifier.
            category: Filter by category (optional).
            min_confidence: Minimum confidence threshold.

        Returns:
            List of MemoryItem objects.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            key_condition = Key('PK').eq(f"USER#{user_id}")

            if category:
                key_condition = key_condition & Key('SK').begins_with(f"MEMORY#{category}#")
            else:
                key_condition = key_condition & Key('SK').begins_with("MEMORY#")

            response = await table.query(
                KeyConditionExpression=key_condition,
            )

            memories = [MemoryItem.from_dynamo_item(item) for item in response.get('Items', [])]

            # Filter by confidence
            if min_confidence > 0:
                memories = [m for m in memories if m.confidence >= min_confidence]

            return memories

    async def get_all_memories(self, user_id: str) -> List[MemoryItem]:
        """
        Get all memories for a user.

        Args:
            user_id: User identifier.

        Returns:
            List of all MemoryItem objects.
        """
        return await self.query_memories(user_id)

    async def delete_memory(
        self,
        user_id: str,
        category: str,
        key: str,
    ) -> bool:
        """
        Delete a memory item.

        Args:
            user_id: User identifier.
            category: Memory category.
            key: Memory key.

        Returns:
            True if deleted, False if not found.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            try:
                await table.delete_item(
                    Key={
                        'PK': f"USER#{user_id}",
                        'SK': f"MEMORY#{category}#{key}",
                    },
                    ConditionExpression="attribute_exists(PK)",
                )
                logger.debug(f"Deleted memory {category}/{key} for user {user_id}")
                return True
            except Exception as e:
                if 'ConditionalCheckFailedException' in str(type(e).__name__):
                    return False
                raise

    async def boost_memory_confidence(
        self,
        user_id: str,
        category: str,
        key: str,
        boost: float = 0.1,
    ) -> Optional[MemoryItem]:
        """
        Boost confidence of a memory item.

        Args:
            user_id: User identifier.
            category: Memory category.
            key: Memory key.
            boost: Amount to boost (0.0-1.0).

        Returns:
            Updated MemoryItem or None if not found.
        """
        memory = await self.get_memory(user_id, category, key)
        if not memory:
            return None

        new_confidence = min(1.0, memory.confidence + boost)

        return await self.put_memory(
            user_id=user_id,
            category=category,
            key=key,
            value=memory.value,
            confidence=new_confidence,
            source=memory.source,
            learned_by=memory.learned_by,
            evidence=memory.evidence,
        )

    async def decay_memories(
        self,
        user_id: str,
        decay_rate: float = 0.01,
    ) -> int:
        """
        Apply confidence decay to all memories.

        Args:
            user_id: User identifier.
            decay_rate: Amount to decay confidence by.

        Returns:
            Number of memories updated.
        """
        memories = await self.get_all_memories(user_id)
        updated = 0

        for memory in memories:
            new_confidence = max(0.0, memory.confidence - decay_rate)
            if new_confidence != memory.confidence:
                await self.put_memory(
                    user_id=memory.user_id,
                    category=memory.category,
                    key=memory.key,
                    value=memory.value,
                    confidence=new_confidence,
                    source=memory.source,
                    learned_by=memory.learned_by,
                    evidence=memory.evidence,
                )
                updated += 1

        logger.info(f"Decayed {updated} memories for user {user_id}")
        return updated

    # ========== Temporary Data Operations ==========

    async def put_temp(
        self,
        session_id: str,
        key: str,
        value: Any,
        ttl_seconds: int = TTL_TMP_SECONDS,
    ) -> None:
        """
        Store temporary session data with TTL.

        Args:
            session_id: Session identifier.
            key: Data key.
            value: Data value (will be stored as JSON-serializable).
            ttl_seconds: Time-to-live in seconds.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            await table.put_item(
                Item={
                    'PK': f"SESSION#{session_id}",
                    'SK': f"TMP#{key}",
                    'entity_type': 'TMP',
                    'session_id': session_id,
                    'key': key,
                    'value': value,
                    'created_at': datetime.now().isoformat(),
                    'ttl': int(time.time()) + ttl_seconds,
                }
            )

    async def get_temp(self, session_id: str, key: str) -> Optional[Any]:
        """
        Get temporary session data.

        Args:
            session_id: Session identifier.
            key: Data key.

        Returns:
            Stored value or None if not found/expired.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            response = await table.get_item(
                Key={
                    'PK': f"SESSION#{session_id}",
                    'SK': f"TMP#{key}",
                }
            )

            item = response.get('Item')
            if item:
                # Check if expired (TTL might not be immediately enforced)
                ttl = item.get('ttl')
                if ttl and int(time.time()) > ttl:
                    return None
                return item.get('value')
            return None

    async def delete_temp(self, session_id: str, key: str) -> None:
        """
        Delete temporary session data.

        Args:
            session_id: Session identifier.
            key: Data key.
        """
        async with self._client.resource() as dynamodb:
            table = await dynamodb.Table(self._table_name)

            await table.delete_item(
                Key={
                    'PK': f"SESSION#{session_id}",
                    'SK': f"TMP#{key}",
                }
            )
