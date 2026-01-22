#!/usr/bin/env python3
"""
Fix existing content items by extracting bilingual fields from analysis_result.

The analysis_result field inside each content document already has:
- title (English)
- title_kr (Korean)
- description (English)
- description_kr (Korean)

This script copies these to the top-level fields.
"""

import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.cosmos import CosmosClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")
load_dotenv()


def get_cosmos_client():
    """Get Cosmos DB client from connection string."""
    connection_string = os.getenv("COSMOS_CONNECTION_STRING")
    
    if not connection_string:
        raise ValueError("COSMOS_CONNECTION_STRING not set in environment")
    
    return CosmosClient.from_connection_string(connection_string)


def fix_content_bilingual():
    """Fix content items by extracting bilingual fields from analysis_result."""
    
    print("🔗 Connecting to Azure Cosmos DB...")
    
    client = get_cosmos_client()
    database_name = os.getenv("COSMOS_DATABASE_NAME", "buildflow")
    database = client.get_database_client(database_name)
    contents_container = database.get_container_client("contents")
    
    # Query all content items
    query = "SELECT * FROM c"
    
    contents = list(contents_container.query_items(query, enable_cross_partition_query=True))
    print(f"📊 Found {len(contents)} content items")
    
    updated_count = 0
    for content in contents:
        content_id = content.get("id")
        analysis_result = content.get("analysis_result", {})
        
        if not analysis_result:
            print(f"   ⚠️ {content_id}: No analysis_result, skipping")
            continue
        
        # Extract bilingual fields from analysis_result
        en_title = analysis_result.get("title")
        kr_title = analysis_result.get("title_kr")
        en_desc = analysis_result.get("description")
        kr_desc = analysis_result.get("description_kr")
        
        print(f"\n📝 Content: {content_id}")
        print(f"   EN title: {en_title[:50] if en_title else 'None'}...")
        print(f"   KR title: {kr_title[:30] if kr_title else 'None'}...")
        
        # Update content with proper bilingual fields
        # title = English, title_kr = Korean
        content["title"] = en_title or content.get("title")
        content["title_kr"] = kr_title
        content["description"] = en_desc or content.get("description")
        content["description_kr"] = kr_desc
        
        # Also extract other fields from analysis_result
        if analysis_result.get("technologies"):
            content["technologies"] = analysis_result["technologies"]
        if analysis_result.get("prerequisites"):
            content["prerequisites"] = analysis_result["prerequisites"]
        if analysis_result.get("learning_objectives"):
            content["learning_outcomes"] = analysis_result["learning_objectives"]
        
        # Upsert the updated content
        try:
            contents_container.upsert_item(content)
            print(f"   ✅ Updated successfully")
            updated_count += 1
        except Exception as e:
            print(f"   ❌ Failed to update: {e}")
    
    print(f"\n🎉 Updated {updated_count} content items with bilingual fields")


if __name__ == "__main__":
    fix_content_bilingual()
