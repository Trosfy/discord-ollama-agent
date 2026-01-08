#!/usr/bin/env python3
"""Check admin_metrics table contents."""

import asyncio
import aioboto3
import os
from datetime import datetime, timedelta
import json
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder for Decimal values."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


async def check_metrics():
    """Query and display metrics from admin_metrics table."""

    session = aioboto3.Session()

    async with session.resource(
        'dynamodb',
        endpoint_url=os.getenv('DYNAMODB_ENDPOINT', 'http://localhost:8000'),
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID', 'test'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', 'test')
    ) as dynamodb:

        table = await dynamodb.Table('admin_metrics')

        print("=" * 80)
        print("Admin Metrics Table Contents")
        print("=" * 80)

        # Scan the table (get all items)
        response = await table.scan(Limit=50)
        items = response.get('Items', [])

        if not items:
            print("\n❌ No items found in admin_metrics table")
            return

        print(f"\n📊 Found {len(items)} items\n")

        # Group by metric type
        metrics_by_type = {}
        for item in items:
            pk = item.get('PK', '')
            metric_type = pk.split('#')[0] if '#' in pk else 'unknown'

            if metric_type not in metrics_by_type:
                metrics_by_type[metric_type] = []
            metrics_by_type[metric_type].append(item)

        # Display summary
        print("Metric Types Found:")
        for metric_type, items_list in metrics_by_type.items():
            print(f"  • {metric_type}: {len(items_list)} items")

        print("\n" + "-" * 80)

        # Show recent items for each type
        for metric_type, items_list in sorted(metrics_by_type.items()):
            print(f"\n📈 {metric_type.upper()} Metrics (showing latest 3):")
            print("-" * 80)

            # Sort by SK (timestamp) descending
            sorted_items = sorted(items_list, key=lambda x: x.get('SK', ''), reverse=True)

            for item in sorted_items[:3]:
                print(f"\n  Timestamp: {item.get('SK', 'N/A')}")
                print(f"  PK: {item.get('PK', 'N/A')}")

                # Show data field with pretty printing
                data = item.get('data', {})
                if data:
                    print(f"  Data:")
                    data_json = json.dumps(data, indent=4, cls=DecimalEncoder)
                    for line in data_json.split('\n'):
                        print(f"    {line}")

                # Show TTL
                ttl = item.get('ttl')
                if ttl:
                    ttl_dt = datetime.fromtimestamp(int(ttl))
                    expires_in = ttl_dt - datetime.now()
                    print(f"  TTL: {ttl_dt.isoformat()} (expires in {expires_in})")

        print("\n" + "=" * 80)

        # Show table info
        table_desc = await table.meta.client.describe_table(TableName='admin_metrics')
        table_info = table_desc['Table']

        print("\nTable Info:")
        print(f"  Item Count: {table_info.get('ItemCount', 'N/A')}")
        print(f"  Size: {table_info.get('TableSizeBytes', 0)} bytes")
        print(f"  Status: {table_info.get('TableStatus', 'N/A')}")

        # Check TTL status
        ttl_response = await table.meta.client.describe_time_to_live(TableName='admin_metrics')
        ttl_status = ttl_response.get('TimeToLiveDescription', {})
        print(f"\nTTL Status:")
        print(f"  Enabled: {ttl_status.get('TimeToLiveStatus', 'Unknown')}")
        print(f"  Attribute: {ttl_status.get('AttributeName', 'None')}")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(check_metrics())
