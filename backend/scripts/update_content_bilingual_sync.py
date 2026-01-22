#!/usr/bin/env python3
"""
Update existing content items with bilingual fields from analysis_request results.

This script reads analysis_request documents from Cosmos DB and updates
the corresponding content items with title_kr, description_kr fields.
"""

import os
import re
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.cosmos import CosmosClient


def update_content_bilingual():
    """Update content items with bilingual fields from analysis results."""

    # Read .env.local and get the Azure (not localhost) COSMOS_CONNECTION_STRING
    env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.local")
    connection_string = None
    database_name = "buildflow"

    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("COSMOS_CONNECTION_STRING=") and "localhost" not in line:
                    connection_string = line.split("=", 1)[1]
                elif line.startswith("COSMOS_DATABASE_NAME="):
                    database_name = line.split("=", 1)[1]

    if not connection_string:
        print("❌ Azure COSMOS_CONNECTION_STRING not found in .env.local")
        return

    # Parse endpoint from connection string
    endpoint_match = re.search(r'AccountEndpoint=([^;]+)', connection_string)
    key_match = re.search(r'AccountKey=([^;]+)', connection_string)

    if not endpoint_match or not key_match:
        print("❌ Invalid COSMOS_CONNECTION_STRING format")
        return

    cosmos_endpoint = endpoint_match.group(1)
    cosmos_key = key_match.group(1)

    print(f"🔗 Connecting to Cosmos DB: {cosmos_endpoint}")

    # Use synchronous client
    client = CosmosClient(cosmos_endpoint, cosmos_key)
    database = client.get_database_client(database_name)

    # Get containers (note: Azure uses 'contents' plural)
    analysis_container = database.get_container_client("analysis_requests")
    content_container = database.get_container_client("contents")

    # Query all completed analysis requests with results
    query = "SELECT * FROM c WHERE c.status = 'completed' AND c.result != null"

    analysis_requests = list(analysis_container.query_items(
        query=query,
        enable_cross_partition_query=True
    ))

    print(f"📊 Found {len(analysis_requests)} completed analysis requests")

    updated_count = 0
    for ar in analysis_requests:
        result = ar.get("result", {})
        content_ids = ar.get("content_ids", [])

        title = result.get("title")
        title_kr = result.get("title_kr")
        description = result.get("description")
        description_kr = result.get("description_kr")

        print(f"\n📝 Analysis: {ar.get('id')[:20]}...")
        print(f"   title: {title[:50] if title else 'None'}...")
        print(f"   title_kr: {title_kr[:30] if title_kr else 'None'}...")
        print(f"   content_ids: {content_ids}")

        for content_id in content_ids:
            try:
                # Read content item (partition key is /id)
                content = content_container.read_item(
                    item=content_id,
                    partition_key=content_id
                )

                # Update with bilingual fields
                content["title"] = title or content.get("title")
                content["title_kr"] = title_kr
                content["description"] = description or content.get("description")
                content["description_kr"] = description_kr

                # Also copy prerequisites and learning_objectives if available
                if result.get("prerequisites"):
                    content["prerequisites"] = result["prerequisites"]
                if result.get("learning_objectives"):
                    content["learning_outcomes"] = result["learning_objectives"]
                if result.get("technologies"):
                    content["technologies"] = result["technologies"]

                # Upsert the updated content
                content_container.upsert_item(content)

                print(f"   ✅ Updated content {content_id}")
                updated_count += 1

            except Exception as e:
                print(f"   ❌ Failed to update content {content_id}: {e}")

    print(f"\n🎉 Updated {updated_count} content items with bilingual fields")


if __name__ == "__main__":
    update_content_bilingual()
