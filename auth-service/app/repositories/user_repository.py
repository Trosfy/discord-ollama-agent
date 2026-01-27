"""DynamoDB user repository implementation"""
import aioboto3
import os
from typing import Optional
from datetime import datetime
from contextlib import asynccontextmanager
from app.interfaces.user_repository import IUserRepository
from app.domain.user import User


class DynamoDBUserRepository(IUserRepository):
    """DynamoDB implementation of user repository"""

    def __init__(self):
        self.endpoint = os.getenv('DYNAMODB_ENDPOINT', 'http://dynamodb-local:8000')
        self.region = os.getenv('DYNAMODB_REGION', 'us-east-1')
        self.access_key = os.getenv('DYNAMODB_ACCESS_KEY', 'test')
        self.secret_key = os.getenv('DYNAMODB_SECRET_KEY', 'test')
        self.table_name = 'users'
        self._session = aioboto3.Session()

    @asynccontextmanager
    async def _get_table(self):
        """Get table within a context manager to properly manage the session lifecycle."""
        async with self._session.resource(
            'dynamodb',
            endpoint_url=self.endpoint,
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        ) as dynamodb:
            table = await dynamodb.Table(self.table_name)
            yield table

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with self._get_table() as table:
            response = await table.get_item(Key={'user_id': user_id})

            if 'Item' not in response:
                return None

            item = response['Item']
            return User(
                user_id=item['user_id'],
                display_name=item['display_name'],
                role=item['role'],
                user_tier=item['user_tier'],
                preferences=item.get('preferences', {}),
                weekly_token_budget=item['weekly_token_budget'],
                tokens_remaining=item['tokens_remaining'],
                tokens_used_this_week=item['tokens_used_this_week'],
                created_at=datetime.fromisoformat(item['created_at']),
                updated_at=datetime.fromisoformat(item['updated_at']),
                email=item.get('email')
            )

    async def create(self, user: User) -> User:
        """Create new user"""
        async with self._get_table() as table:
            item = {
                'user_id': user.user_id,
                'display_name': user.display_name,
                'role': user.role,
                'user_tier': user.user_tier,
                'preferences': user.preferences,
                'weekly_token_budget': user.weekly_token_budget,
                'tokens_remaining': user.tokens_remaining,
                'tokens_used_this_week': user.tokens_used_this_week,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat()
            }

            if user.email:
                item['email'] = user.email

            await table.put_item(Item=item)
            return user

    async def update(self, user: User) -> User:
        """Update existing user"""
        async with self._get_table() as table:
            update_expr = 'SET display_name = :dn, #role = :role, user_tier = :tier, preferences = :prefs, '
            update_expr += 'weekly_token_budget = :wtb, tokens_remaining = :tr, '
            update_expr += 'tokens_used_this_week = :tutw, updated_at = :ua'

            expr_values = {
                ':dn': user.display_name,
                ':role': user.role,
                ':tier': user.user_tier,
                ':prefs': user.preferences,
                ':wtb': user.weekly_token_budget,
                ':tr': user.tokens_remaining,
                ':tutw': user.tokens_used_this_week,
                ':ua': user.updated_at.isoformat()
            }

            expr_names = {'#role': 'role'}

            if user.email:
                update_expr += ', email = :email'
                expr_values[':email'] = user.email

            await table.update_item(
                Key={'user_id': user.user_id},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_values
            )

            return user

    async def delete(self, user_id: str) -> bool:
        """Delete user"""
        async with self._get_table() as table:
            await table.delete_item(Key={'user_id': user_id})
            return True
