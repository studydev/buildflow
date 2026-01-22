#!/usr/bin/env python3
"""List containers in Azure Cosmos DB."""

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

# List all containers
print("\n📦 Containers in 'buildflow' database:")
for container_props in database.list_containers():
    print(f"  - {container_props['id']} (partition key: {container_props.get('partitionKey', {}).get('paths', ['unknown'])})")
