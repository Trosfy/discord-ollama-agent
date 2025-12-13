"""Conversation storage implementation using DynamoDB.

This class implements IConversationStorage.
For user data (preferences, tokens), use UserStorage instead.
"""
import aioboto3
from datetime import datetime, timezone
from typing import List, Dict, Optional
from botocore.exceptions import ClientError

from app.config import settings

# DynamoDB item size limit is 400KB - keep messages under 300KB to be safe
MAX_MESSAGE_SIZE = 300 * 1024  # 300KB


class ConversationStorage:
    """
    Conversation history storage using DynamoDB.

    Single Responsibility: Manage conversation threads and messages
    Implements: IConversationStorage

    Note: For user data (preferences, token tracking), use UserStorage instead
          (app.implementations.user_storage).
    """

    def __init__(self):
        self.session = aioboto3.Session()
        self._resource_config = {
            'endpoint_url': settings.DYNAMODB_ENDPOINT,
            'region_name': settings.DYNAMODB_REGION,
            'aws_access_key_id': settings.DYNAMODB_ACCESS_KEY,
            'aws_secret_access_key': settings.DYNAMODB_SECRET_KEY
        }

    async def initialize_tables(self):
        """Create tables if they don't exist."""
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            await self._create_conversations_table(dynamodb)
            await self._create_users_table(dynamodb)

    async def _create_conversations_table(self, dynamodb):
        """Create conversations table with GSI."""
        try:
            table = await dynamodb.create_table(
                TableName='conversations',
                KeySchema=[
                    {'AttributeName': 'thread_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'message_timestamp', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'thread_id', 'AttributeType': 'S'},
                    {'AttributeName': 'message_timestamp', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'user_id-message_timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'message_timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        }
                    }
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            await table.wait_until_exists()
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceInUseException':
                raise

    async def _create_users_table(self, dynamodb):
        """
        Create users table.

        Note: This table is used by both DynamoDBStorage (token tracking)
              and UserStorage (user preferences). Should be moved to a
              centralized database initialization script.
        """
        try:
            table = await dynamodb.create_table(
                TableName='users',
                KeySchema=[
                    {'AttributeName': 'user_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'user_id', 'AttributeType': 'S'}
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            await table.wait_until_exists()
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceInUseException':
                raise

    # ============================================================================
    # Conversation Methods (IConversationStorage)
    # ============================================================================

    async def get_thread_messages(
        self,
        thread_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Get messages for a thread, ordered chronologically."""
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('conversations')

            params = {
                'KeyConditionExpression': 'thread_id = :tid',
                'ExpressionAttributeValues': {':tid': thread_id},
                'ScanIndexForward': True
            }
            if limit:
                params['Limit'] = limit

            response = await table.query(**params)
            return response.get('Items', [])

    async def add_message(
        self,
        thread_id: str,
        message_id: str,
        role: str,
        content: str,
        token_count: int,
        user_id: str,
        model_used: str,
        is_summary: bool = False
    ) -> None:
        """Add a message to a thread."""
        # Truncate content if it exceeds DynamoDB's size limit
        content_bytes = content.encode('utf-8')
        if len(content_bytes) > MAX_MESSAGE_SIZE:
            # Truncate and add marker
            truncated_content = content_bytes[:MAX_MESSAGE_SIZE].decode('utf-8', errors='ignore')
            content = truncated_content + "\n\n... [Message truncated due to size limit]"

        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('conversations')
            await table.put_item(Item={
                'thread_id': thread_id,
                'message_timestamp': datetime.now(timezone.utc).isoformat(),
                'message_id': message_id,
                'role': role,
                'content': content,
                'token_count': token_count,
                'user_id': user_id,
                'model_used': model_used,
                'is_summary': is_summary
            })

    async def delete_messages(
        self,
        thread_id: str,
        message_timestamps: List[str]
    ) -> None:
        """Batch delete messages from a thread."""
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('conversations')
            async with table.batch_writer() as batch:
                for timestamp in message_timestamps:
                    await batch.delete_item(Key={
                        'thread_id': thread_id,
                        'message_timestamp': timestamp
                    })

    async def get_user_threads(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[str]:
        """Get list of thread IDs for a user."""
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('conversations')
            response = await table.query(
                IndexName='user_id-message_timestamp-index',
                KeyConditionExpression='user_id = :uid',
                ExpressionAttributeValues={':uid': user_id},
                ScanIndexForward=False,
                Limit=limit * 10
            )

            thread_ids = list(set(item['thread_id'] for item in response['Items']))
            return thread_ids[:limit]
