"""Fetch all unique categories from Azure AI Search."""

import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv('.env.local')


async def get_categories():
    endpoint = os.getenv('AZURE_SEARCH_ENDPOINT')
    api_key = os.getenv('AZURE_SEARCH_API_KEY')
    index_name = 'buildflow-content'

    if not endpoint or not api_key:
        print('Missing AZURE_SEARCH_ENDPOINT or AZURE_SEARCH_API_KEY')
        return

    url = f'{endpoint}/indexes/{index_name}/docs/search?api-version=2024-07-01'

    headers = {
        'Content-Type': 'application/json',
        'api-key': api_key
    }

    # Facet query to get all unique categories
    body = {
        'search': '*',
        'facets': ['categories'],
        'top': 0
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=body)
        data = response.json()

        if 'error' in data:
            print(f'Error: {data["error"]}')
            return

        facets = data.get('@search.facets', {})
        categories = facets.get('categories', [])

        print('=== Azure AI Search Categories ===')
        for cat in sorted(categories, key=lambda x: -x['count']):
            print(f"  {cat['value']}: {cat['count']} items")
        print(f'\nTotal unique categories: {len(categories)}')


if __name__ == '__main__':
    asyncio.run(get_categories())
