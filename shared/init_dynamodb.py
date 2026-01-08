"""Centralized DynamoDB table initialization for Trollama.

Creates all tables needed by all services:
- users: User profiles (auth-service, fastapi-service)
- auth_methods: Authentication methods (auth-service)
- conversations: Chat history (fastapi-service)
- webpage_chunks: RAG vector storage (fastapi-service)
- admin_metrics: Time-series metrics with 2-day TTL (admin-service)
"""
import asyncio
import aioboto3
import os
from botocore.exceptions import ClientError


async def initialize_all_tables():
    """Create all DynamoDB tables if they don't exist."""

    session = aioboto3.Session()
    resource_config = {
        'endpoint_url': os.getenv('DYNAMODB_ENDPOINT', 'http://localhost:8000'),
        'region_name': os.getenv('DYNAMODB_REGION', 'us-east-1'),
        'aws_access_key_id': os.getenv('DYNAMODB_ACCESS_KEY', 'test'),
        'aws_secret_access_key': os.getenv('DYNAMODB_SECRET_KEY', 'test')
    }

    async with session.resource('dynamodb', **resource_config) as dynamodb:
        tables_created = []

        # 1. Users table (used by auth-service and fastapi-service)
        if await create_users_table(dynamodb):
            tables_created.append('users')

        # 2. Auth methods table (used by auth-service)
        if await create_auth_methods_table(dynamodb):
            tables_created.append('auth_methods')

        # 3. Conversations table (used by fastapi-service)
        if await create_conversations_table(dynamodb):
            tables_created.append('conversations')

        # 4. Webpage chunks table (used by fastapi-service for RAG)
        if await create_webpage_chunks_table(dynamodb):
            tables_created.append('webpage_chunks')

        # 5. Admin metrics table (used by admin-service)
        if await create_admin_metrics_table(dynamodb):
            tables_created.append('admin_metrics')

        return tables_created


async def create_users_table(dynamodb):
    """Create users table for user profiles."""
    try:
        print("Creating 'users' table...")
        table = await dynamodb.create_table(
            TableName='users',
            KeySchema=[
                {'AttributeName': 'user_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'user_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        await table.wait_until_exists()
        print("✅ 'users' table created")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print("✓ 'users' table already exists")
            return False
        raise


async def create_auth_methods_table(dynamodb):
    """Create auth_methods table for authentication."""
    try:
        print("Creating 'auth_methods' table...")
        table = await dynamodb.create_table(
            TableName='auth_methods',
            KeySchema=[
                {'AttributeName': 'auth_method_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'auth_method_id', 'AttributeType': 'S'},
                {'AttributeName': 'user_id', 'AttributeType': 'S'},
                {'AttributeName': 'provider', 'AttributeType': 'S'},
                {'AttributeName': 'provider_user_id', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'user_id-index',
                    'KeySchema': [
                        {'AttributeName': 'user_id', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'provider-provider_user_id-index',
                    'KeySchema': [
                        {'AttributeName': 'provider', 'KeyType': 'HASH'},
                        {'AttributeName': 'provider_user_id', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        await table.wait_until_exists()
        print("✅ 'auth_methods' table created")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print("✓ 'auth_methods' table already exists")
            return False
        raise


async def create_conversations_table(dynamodb):
    """Create conversations table for chat history."""
    try:
        print("Creating 'conversations' table...")
        table = await dynamodb.create_table(
            TableName='conversations',
            KeySchema=[
                {'AttributeName': 'conversation_id', 'KeyType': 'HASH'},
                {'AttributeName': 'message_timestamp', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'conversation_id', 'AttributeType': 'S'},
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
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        await table.wait_until_exists()
        print("✅ 'conversations' table created")
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print("✓ 'conversations' table already exists")
            return False
        raise


async def create_webpage_chunks_table(dynamodb):
    """Create webpage_chunks table for RAG vector storage."""
    try:
        print("Creating 'webpage_chunks' table...")
        table = await dynamodb.create_table(
            TableName='webpage_chunks',
            KeySchema=[
                {'AttributeName': 'url_hash', 'KeyType': 'HASH'},
                {'AttributeName': 'chunk_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'url_hash', 'AttributeType': 'S'},
                {'AttributeName': 'chunk_id', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        await table.wait_until_exists()
        print("✅ 'webpage_chunks' table created")

        # Note: TTL is not supported by DynamoDB Local, but would be enabled in production:
        # await dynamodb_client.update_time_to_live(
        #     TableName='webpage_chunks',
        #     TimeToLiveSpecification={'Enabled': True, 'AttributeName': 'ttl'}
        # )

        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print("✓ 'webpage_chunks' table already exists")
            return False
        raise


async def create_admin_metrics_table(dynamodb):
    """Create admin_metrics table for time-series metrics with 2-day TTL.

    Schema:
    - PK: {metric_type}#{YYYY-MM-DDTHH} (hourly bucketing)
    - SK: ISO timestamp with milliseconds
    - TTL: 2-day retention (172,800 seconds)

    Used by admin-service for storing VRAM, health, PSI, and queue metrics.
    """
    try:
        print("Creating 'admin_metrics' table...")
        table = await dynamodb.create_table(
            TableName='admin_metrics',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},   # Partition key
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}   # Sort key
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand pricing
        )
        await table.wait_until_exists()

        # Enable TTL for 2-day retention
        try:
            client = dynamodb.meta.client
            await client.update_time_to_live(
                TableName='admin_metrics',
                TimeToLiveSpecification={
                    'Enabled': True,
                    'AttributeName': 'ttl'
                }
            )
            print("✅ 'admin_metrics' table created with TTL enabled (2-day retention)")
        except Exception as ttl_error:
            print(f"✅ 'admin_metrics' table created (TTL not enabled: {ttl_error})")

        return True
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print("✓ 'admin_metrics' table already exists")
            return False
        raise


async def main():
    """Main entry point."""
    print("=== Trollama DynamoDB Initialization ===\n")

    try:
        tables_created = await initialize_all_tables()

        print("\n=== Summary ===")
        if tables_created:
            print(f"Created {len(tables_created)} new table(s): {', '.join(tables_created)}")
        else:
            print("All tables already exist")

        print("\n✅ Database initialization complete!")

    except Exception as e:
        print(f"\n❌ Error initializing tables: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
