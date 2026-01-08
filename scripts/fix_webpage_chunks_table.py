"""Delete and recreate webpage_chunks table with correct schema."""
import asyncio
import aioboto3
import os
import sys
from botocore.exceptions import ClientError

sys.path.insert(0, '/shared')


async def fix_table():
    """Delete and recreate webpage_chunks table."""

    session = aioboto3.Session()
    resource_config = {
        'endpoint_url': os.getenv('DYNAMODB_ENDPOINT', 'http://dynamodb-local:8000'),
        'region_name': os.getenv('DYNAMODB_REGION', 'us-east-1'),
        'aws_access_key_id': os.getenv('DYNAMODB_ACCESS_KEY', 'fake'),
        'aws_secret_access_key': os.getenv('DYNAMODB_SECRET_KEY', 'fake')
    }

    async with session.resource('dynamodb', **resource_config) as dynamodb:
        # Delete existing table
        try:
            print("Deleting old 'webpage_chunks' table...")
            table = await dynamodb.Table('webpage_chunks')
            await table.delete()
            await table.wait_until_not_exists()
            print("✅ Old table deleted")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print("✓ Table doesn't exist, proceeding to create")
            else:
                raise

        # Create new table with correct schema
        try:
            print("Creating new 'webpage_chunks' table with url_hash partition key...")
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
            print("✅ New table created with correct schema")

            # Try to enable TTL (may not work in DynamoDB Local)
            try:
                client = await session.client('dynamodb', **resource_config).__aenter__()
                await client.update_time_to_live(
                    TableName='webpage_chunks',
                    TimeToLiveSpecification={
                        'Enabled': True,
                        'AttributeName': 'ttl'
                    }
                )
                print("✅ TTL enabled on 'ttl' attribute")
            except Exception as e:
                print(f"⚠️  TTL not enabled (DynamoDB Local limitation): {e}")

        except ClientError as e:
            print(f"❌ Error creating table: {e}")
            raise


if __name__ == "__main__":
    print("=== Fix webpage_chunks Table Schema ===\n")
    asyncio.run(fix_table())
    print("\n✅ Done!")
