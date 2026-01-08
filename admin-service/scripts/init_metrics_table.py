#!/usr/bin/env python3
"""
Initialize DynamoDB Metrics Table

Creates the admin_metrics table with proper configuration:
- Partition key (PK): {metric_type}#{YYYY-MM-DDTHH}
- Sort key (SK): ISO timestamp
- TTL enabled on 'ttl' attribute
- On-demand billing mode

Usage:
    python scripts/init_metrics_table.py

Environment Variables:
    DYNAMODB_ENDPOINT - DynamoDB endpoint URL (default: http://localhost:8000)
    AWS_REGION - AWS region (default: us-east-1)
    AWS_ACCESS_KEY_ID - AWS access key (default: dummy for local)
    AWS_SECRET_ACCESS_KEY - AWS secret key (default: dummy for local)
"""

import os
import sys
import asyncio
import aioboto3
from datetime import datetime


# Configuration
TABLE_NAME = "admin_metrics"
DYNAMODB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8000")
DYNAMODB_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "dummy")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "dummy")


async def check_table_exists(dynamodb) -> bool:
    """Check if the metrics table already exists."""
    try:
        table = await dynamodb.Table(TABLE_NAME)
        await table.load()
        return True
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        return False
    except Exception as e:
        print(f"❌ Error checking table existence: {e}")
        return False


async def create_table(dynamodb) -> bool:
    """Create the metrics table with proper configuration."""
    try:
        print(f"📊 Creating table {TABLE_NAME}...")

        table = await dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {
                    "AttributeName": "PK",
                    "KeyType": "HASH"  # Partition key
                },
                {
                    "AttributeName": "SK",
                    "KeyType": "RANGE"  # Sort key
                }
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "PK",
                    "AttributeType": "S"  # String
                },
                {
                    "AttributeName": "SK",
                    "AttributeType": "S"  # String
                }
            ],
            BillingMode="PAY_PER_REQUEST",  # On-demand pricing
        )

        # Wait for table to be created
        print("⏳ Waiting for table to be created...")
        await table.meta.client.get_waiter("table_exists").wait(
            TableName=TABLE_NAME
        )

        print(f"✅ Table {TABLE_NAME} created successfully")
        return True

    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False


async def enable_ttl(dynamodb) -> bool:
    """Enable TTL on the table."""
    try:
        print("⏱️  Enabling TTL on 'ttl' attribute...")

        client = dynamodb.meta.client

        # Update TTL settings
        await client.update_time_to_live(
            TableName=TABLE_NAME,
            TimeToLiveSpecification={
                "Enabled": True,
                "AttributeName": "ttl"
            }
        )

        print("✅ TTL enabled successfully (2-day retention)")
        return True

    except Exception as e:
        print(f"❌ Error enabling TTL: {e}")
        return False


async def write_test_data(dynamodb) -> bool:
    """Write a test metric to verify table is working."""
    try:
        print("🧪 Writing test metric...")

        table = await dynamodb.Table(TABLE_NAME)

        test_item = {
            "PK": f"test#{datetime.utcnow().strftime('%Y-%m-%dT%H')}",
            "SK": datetime.utcnow().isoformat() + "Z",
            "ttl": int(datetime.utcnow().timestamp()) + 60,  # Expire in 1 minute
            "entity_type": "metric",
            "metric_type": "test",
            "data": {
                "test_value": 42.0,
                "message": "This is a test metric that will expire in 1 minute"
            }
        }

        await table.put_item(Item=test_item)

        print("✅ Test metric written successfully")
        print(f"   PK: {test_item['PK']}")
        print(f"   SK: {test_item['SK']}")
        print("   Note: This test item will expire in 1 minute")
        return True

    except Exception as e:
        print(f"❌ Error writing test data: {e}")
        return False


async def show_table_info(dynamodb) -> bool:
    """Display table information."""
    try:
        client = dynamodb.meta.client

        # Get table description
        response = await client.describe_table(TableName=TABLE_NAME)
        table_info = response["Table"]

        print("\n📋 Table Information:")
        print(f"   Name: {table_info['TableName']}")
        print(f"   Status: {table_info['TableStatus']}")
        print(f"   Items: {table_info.get('ItemCount', 'N/A')}")
        print(f"   Size: {table_info.get('TableSizeBytes', 0)} bytes")
        print(f"   Billing: {table_info.get('BillingModeSummary', {}).get('BillingMode', 'N/A')}")

        # Get TTL status
        ttl_response = await client.describe_time_to_live(TableName=TABLE_NAME)
        ttl_status = ttl_response.get("TimeToLiveDescription", {})

        print(f"\n⏱️  TTL Configuration:")
        print(f"   Status: {ttl_status.get('TimeToLiveStatus', 'Unknown')}")
        print(f"   Attribute: {ttl_status.get('AttributeName', 'None')}")

        print(f"\n🔑 Key Schema:")
        for key in table_info["KeySchema"]:
            print(f"   {key['AttributeName']}: {key['KeyType']}")

        return True

    except Exception as e:
        print(f"❌ Error getting table info: {e}")
        return False


async def main():
    """Main initialization function."""
    print("=" * 60)
    print("DynamoDB Metrics Table Initialization")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Endpoint: {DYNAMODB_ENDPOINT}")
    print(f"  Region: {DYNAMODB_REGION}")
    print(f"  Table: {TABLE_NAME}")
    print()

    session = aioboto3.Session()

    async with session.resource(
        "dynamodb",
        region_name=DYNAMODB_REGION,
        endpoint_url=DYNAMODB_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    ) as dynamodb:

        # Check if table exists
        exists = await check_table_exists(dynamodb)

        if exists:
            print(f"ℹ️  Table {TABLE_NAME} already exists")

            # Show table info
            await show_table_info(dynamodb)

            # Ask if user wants to write test data
            response = input("\nWrite test data? (y/n): ")
            if response.lower() == "y":
                await write_test_data(dynamodb)

        else:
            # Create new table
            success = await create_table(dynamodb)

            if not success:
                print("\n❌ Failed to create table")
                return 1

            # Enable TTL
            await enable_ttl(dynamodb)

            # Show table info
            await show_table_info(dynamodb)

            # Write test data
            await write_test_data(dynamodb)

        print("\n" + "=" * 60)
        print("✅ Initialization complete!")
        print("=" * 60)

        return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
