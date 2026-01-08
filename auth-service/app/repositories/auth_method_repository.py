"""DynamoDB auth_method repository implementation"""
import aioboto3
import os
from typing import Optional, List
from datetime import datetime
from app.interfaces.auth_method_repository import IAuthMethodRepository
from app.domain.auth_method import AuthMethod


class DynamoDBAuthMethodRepository(IAuthMethodRepository):
    """DynamoDB implementation of auth method repository"""

    def __init__(self):
        self.endpoint = os.getenv('DYNAMODB_ENDPOINT', 'http://dynamodb-local:8000')
        self.region = os.getenv('DYNAMODB_REGION', 'us-east-1')
        self.access_key = os.getenv('DYNAMODB_ACCESS_KEY', 'test')
        self.secret_key = os.getenv('DYNAMODB_SECRET_KEY', 'test')
        self.table_name = 'auth_methods'

    async def _get_table(self):
        session = aioboto3.Session()
        resource = session.resource(
            'dynamodb',
            endpoint_url=self.endpoint,
            region_name=self.region,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )
        async with resource as dynamodb:
            return await dynamodb.Table(self.table_name)

    def _item_to_auth_method(self, item: dict) -> AuthMethod:
        """Convert DynamoDB item to AuthMethod domain object"""
        return AuthMethod(
            auth_method_id=item['auth_method_id'],
            user_id=item['user_id'],
            provider=item['provider'],
            provider_user_id=item['provider_user_id'],
            credentials=item.get('credentials', {}),
            metadata=item.get('metadata', {}),
            is_primary=item.get('is_primary', False),
            is_verified=item.get('is_verified', True),
            created_at=datetime.fromisoformat(item['created_at']),
            last_used_at=datetime.fromisoformat(item['last_used_at']) if item.get('last_used_at') else None
        )

    async def get_by_id(self, auth_method_id: str) -> Optional[AuthMethod]:
        """Get auth method by ID"""
        table = await self._get_table()
        response = await table.get_item(Key={'auth_method_id': auth_method_id})

        if 'Item' not in response:
            return None

        return self._item_to_auth_method(response['Item'])

    async def get_by_provider_and_identifier(
        self,
        provider: str,
        provider_user_id: str
    ) -> Optional[AuthMethod]:
        """Get auth method by provider + identifier using GSI"""
        table = await self._get_table()

        response = await table.query(
            IndexName='provider-provider_user_id-index',
            KeyConditionExpression='provider = :provider AND provider_user_id = :puid',
            ExpressionAttributeValues={
                ':provider': provider,
                ':puid': provider_user_id
            }
        )

        items = response.get('Items', [])
        if not items:
            return None

        return self._item_to_auth_method(items[0])

    async def get_all_for_user(self, user_id: str) -> List[AuthMethod]:
        """Get all auth methods for a user using GSI"""
        table = await self._get_table()

        response = await table.query(
            IndexName='user_id-index',
            KeyConditionExpression='user_id = :uid',
            ExpressionAttributeValues={':uid': user_id}
        )

        items = response.get('Items', [])
        return [self._item_to_auth_method(item) for item in items]

    async def create(self, auth_method: AuthMethod) -> AuthMethod:
        """Create new auth method"""
        table = await self._get_table()

        item = {
            'auth_method_id': auth_method.auth_method_id,
            'user_id': auth_method.user_id,
            'provider': auth_method.provider,
            'provider_user_id': auth_method.provider_user_id,
            'credentials': auth_method.credentials,
            'metadata': auth_method.metadata,
            'is_primary': auth_method.is_primary,
            'is_verified': auth_method.is_verified,
            'created_at': auth_method.created_at.isoformat()
        }

        if auth_method.last_used_at:
            item['last_used_at'] = auth_method.last_used_at.isoformat()

        await table.put_item(Item=item)
        return auth_method

    async def update(self, auth_method: AuthMethod) -> AuthMethod:
        """Update auth method"""
        table = await self._get_table()

        update_expr = 'SET credentials = :creds, metadata = :meta, '
        update_expr += 'is_primary = :primary, is_verified = :verified'

        expr_values = {
            ':creds': auth_method.credentials,
            ':meta': auth_method.metadata,
            ':primary': auth_method.is_primary,
            ':verified': auth_method.is_verified
        }

        if auth_method.last_used_at:
            update_expr += ', last_used_at = :last_used'
            expr_values[':last_used'] = auth_method.last_used_at.isoformat()

        await table.update_item(
            Key={'auth_method_id': auth_method.auth_method_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )

        return auth_method

    async def delete(self, auth_method_id: str) -> bool:
        """Delete auth method"""
        table = await self._get_table()
        await table.delete_item(Key={'auth_method_id': auth_method_id})
        return True
