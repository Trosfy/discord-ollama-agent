"""DynamoDB implementation of StorageInterface using aioboto3."""
import aioboto3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from botocore.exceptions import ClientError

from app.interfaces.storage import StorageInterface
from app.config import settings


class DynamoDBStorage(StorageInterface):
    """DynamoDB Local storage implementation with async operations."""

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
        """Create users table."""
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

    async def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user data."""
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            response = await table.get_item(Key={'user_id': user_id})
            return response.get('Item')

    async def create_user(
        self,
        user_id: str,
        discord_username: str,
        user_tier: str = 'free'
    ) -> None:
        """Create a new user with default settings."""
        weekly_budget = (
            settings.ADMIN_TIER_WEEKLY_BUDGET
            if user_tier == 'admin'
            else settings.FREE_TIER_WEEKLY_BUDGET
        )

        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            await table.put_item(Item={
                'user_id': user_id,
                'discord_username': discord_username,
                'user_tier': user_tier,
                'preferred_model': settings.OLLAMA_DEFAULT_MODEL,
                'temperature': '0.7',  # DynamoDB stores as Decimal, use string
                'base_prompt': None,
                'weekly_token_budget': weekly_budget,
                'bonus_tokens': 0,
                'tokens_used_this_week': 0,
                'tokens_remaining': weekly_budget,
                'week_start_date': self._get_week_start(),
                'auto_summarize_threshold': settings.DEFAULT_SUMMARIZATION_THRESHOLD,
                'notify_on_summarization': True,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_active': datetime.now(timezone.utc).isoformat()
            })

    async def update_user_tokens(self, user_id: str, tokens_used: int) -> None:
        """Update user's token usage."""
        user = await self.get_user(user_id)
        if not user:
            return

        new_used = int(user['tokens_used_this_week']) + tokens_used
        new_remaining = (
            int(user['weekly_token_budget']) +
            int(user['bonus_tokens']) -
            new_used
        )

        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            await table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET tokens_used_this_week = :used, '
                               'tokens_remaining = :remaining, '
                               'last_active = :now',
                ExpressionAttributeValues={
                    ':used': new_used,
                    ':remaining': max(0, new_remaining),
                    ':now': datetime.now(timezone.utc).isoformat()
                }
            )

    async def grant_bonus_tokens(self, user_id: str, amount: int) -> None:
        """Grant bonus tokens to a user."""
        async with self.session.resource('dynamodb', **self._resource_config) as dynamodb:
            table = await dynamodb.Table('users')
            await table.update_item(
                Key={'user_id': user_id},
                UpdateExpression='SET bonus_tokens = bonus_tokens + :amount',
                ExpressionAttributeValues={':amount': amount}
            )

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

    def _get_week_start(self) -> str:
        """Get Monday of current week."""
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        return monday.isoformat()
