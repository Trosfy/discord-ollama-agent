"""DynamoDB vector storage for webpage chunks with embeddings."""
import hashlib
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
import aioboto3
from botocore.exceptions import ClientError

from app.interfaces.storage import VectorChunk, IVectorStorage
from app.config import settings
import logging_client

logger = logging_client.setup_logger('vector_storage')


class DynamoDBVectorStorage:
    """DynamoDB implementation of vector storage with TTL support.

    Implements IVectorStorage following Single Responsibility Principle.
    Uses SHA256 hash of URL as partition key, chunk_id as sort key.

    Note: DynamoDB doesn't support native vector similarity search.
    Uses client-side cosine similarity computation.
    For production scale, consider Pinecone/Weaviate/pgvector.
    """

    def __init__(self):
        """Initialize DynamoDB vector storage."""
        self.session = aioboto3.Session()
        self.table_name = 'webpage_chunks'
        self._dynamodb_config = {
            'region_name': settings.DYNAMODB_REGION,
            'endpoint_url': settings.DYNAMODB_ENDPOINT,
            'aws_access_key_id': settings.DYNAMODB_ACCESS_KEY,
            'aws_secret_access_key': settings.DYNAMODB_SECRET_KEY
        }

        logger.info(
            f"✅ DynamoDBVectorStorage initialized (table={self.table_name})"
        )

    @staticmethod
    def _hash_url(url: str) -> str:
        """Generate SHA256 hash of URL for partition key.

        Args:
            url: Source URL

        Returns:
            SHA256 hash as hex string
        """
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity score (0-1, higher is more similar)
        """
        if len(vec1) != len(vec2):
            raise ValueError(
                f"Vector dimensions must match: {len(vec1)} != {len(vec2)}"
            )

        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    @staticmethod
    def _convert_float_to_decimal(obj):
        """Recursively convert floats to Decimal for DynamoDB compatibility.

        Args:
            obj: Object to convert (can be dict, list, float, or other type)

        Returns:
            Converted object with Decimals instead of floats
        """
        if isinstance(obj, list):
            return [DynamoDBVectorStorage._convert_float_to_decimal(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: DynamoDBVectorStorage._convert_float_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, float):
            return Decimal(str(obj))
        return obj

    @staticmethod
    def _convert_decimal_to_float(obj):
        """Recursively convert Decimal to float when reading from DynamoDB.

        Args:
            obj: Object to convert (can be dict, list, Decimal, or other type)

        Returns:
            Converted object with floats instead of Decimals
        """
        if isinstance(obj, list):
            return [DynamoDBVectorStorage._convert_decimal_to_float(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: DynamoDBVectorStorage._convert_decimal_to_float(v) for k, v in obj.items()}
        elif isinstance(obj, Decimal):
            return float(obj)
        return obj

    async def initialize_table(self):
        """Create webpage_chunks table with TTL enabled.

        Table Schema:
        - PK: url_hash (SHA256 of URL)
        - SK: chunk_id (UUID)
        - Attributes: chunk_text, embedding_vector (List[float]), chunk_index,
                     token_count, source_url, created_at, ttl (Unix timestamp)
        - TTL: Enabled on 'ttl' attribute
        """
        async with self.session.resource('dynamodb', **self._dynamodb_config) as dynamodb:
            try:
                table = await dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {'AttributeName': 'url_hash', 'KeyType': 'HASH'},  # Partition key
                        {'AttributeName': 'chunk_id', 'KeyType': 'RANGE'}  # Sort key
                    ],
                    AttributeDefinitions=[
                        {'AttributeName': 'url_hash', 'AttributeType': 'S'},
                        {'AttributeName': 'chunk_id', 'AttributeType': 'S'}
                    ],
                    BillingMode='PAY_PER_REQUEST'  # On-demand pricing
                )

                await table.wait_until_exists()

                # Enable TTL on the table
                client = await self.session.client('dynamodb', **self._dynamodb_config).__aenter__()
                try:
                    await client.update_time_to_live(
                        TableName=self.table_name,
                        TimeToLiveSpecification={
                            'Enabled': True,
                            'AttributeName': 'ttl'
                        }
                    )
                    logger.info(f"✅ Table '{self.table_name}' created with TTL enabled")
                finally:
                    await client.__aexit__(None, None, None)

            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceInUseException':
                    logger.info(f"ℹ️ Table '{self.table_name}' already exists")
                else:
                    logger.error(f"❌ Error creating table: {e}")
                    raise

    async def store_chunks(
        self,
        url: str,
        chunks: List[Dict],
        ttl_hours: int
    ) -> int:
        """Store webpage chunks with embeddings and TTL.

        Args:
            url: Source URL (will be hashed for partition key)
            chunks: List of dicts with keys: chunk_id, chunk_text, embedding_vector,
                   chunk_index, token_count
            ttl_hours: Time-to-live in hours

        Returns:
            Number of chunks stored

        Raises:
            ValueError: If url or chunks are invalid
        """
        if not url or not url.strip():
            raise ValueError("URL cannot be empty")

        if not chunks:
            raise ValueError("Chunks list cannot be empty")

        url_hash = self._hash_url(url)
        created_at = datetime.utcnow().isoformat()
        ttl_timestamp = int((datetime.utcnow() + timedelta(hours=ttl_hours)).timestamp())

        logger.info(
            f"📦 Storing {len(chunks)} chunks for URL: {url} "
            f"(ttl={ttl_hours}h, expires={datetime.fromtimestamp(ttl_timestamp)})"
        )

        async with self.session.resource('dynamodb', **self._dynamodb_config) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            # Batch write chunks
            async with table.batch_writer() as batch:
                for chunk in chunks:
                    item = {
                        'url_hash': url_hash,
                        'chunk_id': chunk['chunk_id'],
                        'chunk_text': chunk['chunk_text'],
                        'embedding_vector': chunk['embedding_vector'],
                        'chunk_index': chunk['chunk_index'],
                        'token_count': chunk['token_count'],
                        'source_url': url,
                        'created_at': created_at,
                        'ttl': ttl_timestamp
                    }
                    # Convert floats to Decimal for DynamoDB
                    item_converted = self._convert_float_to_decimal(item)
                    await batch.put_item(Item=item_converted)

        logger.info(f"✅ Stored {len(chunks)} chunks for {url}")
        return len(chunks)

    async def get_chunks_by_url(self, url: str) -> Optional[List[VectorChunk]]:
        """Retrieve all chunks for a URL (cache check).

        Filters out expired chunks based on TTL.

        Args:
            url: Source URL to look up

        Returns:
            List of VectorChunk objects if found and not expired, None otherwise
        """
        if not url or not url.strip():
            raise ValueError("URL cannot be empty")

        url_hash = self._hash_url(url)
        current_timestamp = int(datetime.utcnow().timestamp())

        async with self.session.resource('dynamodb', **self._dynamodb_config) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                # Query all chunks for this URL hash
                response = await table.query(
                    KeyConditionExpression='url_hash = :url_hash',
                    ExpressionAttributeValues={':url_hash': url_hash}
                )

                items = response.get('Items', [])

                if not items:
                    logger.debug(f"ℹ️ No chunks found for URL: {url}")
                    return None

                # Filter expired chunks (client-side since DynamoDB may not have cleaned yet)
                valid_chunks = [
                    item for item in items
                    if item.get('ttl', 0) > current_timestamp
                ]

                if not valid_chunks:
                    logger.debug(f"ℹ️ All chunks expired for URL: {url}")
                    return None

                # Convert to VectorChunk objects (convert Decimal to float)
                chunks = [
                    VectorChunk(
                        chunk_id=item['chunk_id'],
                        chunk_text=item['chunk_text'],
                        embedding_vector=self._convert_decimal_to_float(item['embedding_vector']),
                        chunk_index=item['chunk_index'],
                        token_count=item['token_count'],
                        source_url=item['source_url'],
                        created_at=item['created_at'],
                        url_hash=item['url_hash']
                    )
                    for item in valid_chunks
                ]

                logger.info(
                    f"✅ Retrieved {len(chunks)} valid chunks for {url} (cache hit)"
                )
                return chunks

            except ClientError as e:
                logger.error(f"❌ Error retrieving chunks: {e}")
                return None

    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[VectorChunk]:
        """Search for most similar chunks using cosine similarity.

        Note: This performs a full table scan and client-side similarity computation.
        Not suitable for large-scale production. Consider Pinecone/Weaviate/pgvector.

        Args:
            query_embedding: Query vector to compare against
            top_k: Number of top results to return

        Returns:
            List of VectorChunk objects sorted by similarity (highest first)
        """
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty")

        if top_k <= 0:
            raise ValueError("top_k must be positive")

        current_timestamp = int(datetime.utcnow().timestamp())

        async with self.session.resource('dynamodb', **self._dynamodb_config) as dynamodb:
            table = await dynamodb.Table(self.table_name)

            try:
                # Full table scan (inefficient for large datasets)
                response = await table.scan()
                items = response.get('Items', [])

                # Handle pagination if table is large
                while 'LastEvaluatedKey' in response:
                    response = await table.scan(
                        ExclusiveStartKey=response['LastEvaluatedKey']
                    )
                    items.extend(response.get('Items', []))

                if not items:
                    logger.debug("ℹ️ No chunks found in database")
                    return []

                # Filter expired chunks
                valid_items = [
                    item for item in items
                    if item.get('ttl', 0) > current_timestamp
                ]

                if not valid_items:
                    logger.debug("ℹ️ All chunks expired")
                    return []

                # Compute similarities
                similarities = []
                for item in valid_items:
                    try:
                        embedding = item.get('embedding_vector', [])
                        if not embedding:
                            continue

                        # Convert Decimal to float for cosine similarity
                        embedding_float = self._convert_decimal_to_float(embedding)
                        similarity = self._cosine_similarity(query_embedding, embedding_float)
                        similarities.append((similarity, item))
                    except Exception as e:
                        logger.warning(
                            f"⚠️ Error computing similarity for chunk {item.get('chunk_id')}: {e}"
                        )
                        continue

                # Sort by similarity (descending) and take top-K
                similarities.sort(reverse=True, key=lambda x: x[0])
                top_items = similarities[:top_k]

                # Convert to VectorChunk objects (convert Decimal to float)
                chunks = [
                    VectorChunk(
                        chunk_id=item['chunk_id'],
                        chunk_text=item['chunk_text'],
                        embedding_vector=self._convert_decimal_to_float(item['embedding_vector']),
                        chunk_index=item['chunk_index'],
                        token_count=item['token_count'],
                        source_url=item['source_url'],
                        created_at=item['created_at'],
                        url_hash=item['url_hash']
                    )
                    for similarity, item in top_items
                ]

                logger.info(
                    f"✅ Found {len(chunks)} similar chunks "
                    f"(scanned {len(valid_items)} valid chunks, top similarity: {top_items[0][0]:.3f})"
                )

                return chunks

            except ClientError as e:
                logger.error(f"❌ Error searching similar chunks: {e}")
                return []
