#!/usr/bin/env python3
"""Check content container data in Azure Cosmos DB."""

import os
import re

env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env.local")
connection_string = None
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if line.startswith('COSMOS_CONNECTION_STRING=') and 'localhost' not in line:
            connection_string = line.split('=', 1)[1]
            break

if not connection_string:
    print("No Azure connection string found")
    exit(1)

endpoint_match = re.search(r'AccountEndpoint=([^;]+)', connection_string)
key_match = re.search(r'AccountKey=([^;]+)', connection_string)
cosmos_endpoint = endpoint_match.group(1)
cosmos_key = key_match.group(1)

print(f"Connecting to: {cosmos_endpoint}")

from azure.cosmos import CosmosClient

client = CosmosClient(cosmos_endpoint, cosmos_key)
database = client.get_database_client('buildflow')
content_container = database.get_container_client('content')

# List all items
items = list(content_container.query_items(
    'SELECT c.id, c.title, c.title_kr, c.contributor_id FROM c',
    enable_cross_partition_query=True
))
print(f'Found {len(items)} content items in Azure Cosmos DB')
for item in items[:5]:
    title = item.get('title', '')
    title_display = title[:40] if title else 'None'
    print(f"  id: {item.get('id')}")
    print(f"     title: {title_display}...")
    print(f"     title_kr: {item.get('title_kr')}")
    print(f"     contributor_id: {item.get('contributor_id')}")
    print()
