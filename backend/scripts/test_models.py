"""Test available Azure OpenAI model deployments."""
import asyncio
import sys

import httpx

sys.path.insert(0, '/Users/hyounsookim/Desktop/Azure/buildflow/backend')

from app.config import get_settings

settings = get_settings()

async def test_models():
    endpoint = getattr(settings, 'azure_openai_endpoint', 'https://genai-thon-04.openai.azure.com/')
    api_key = getattr(settings, 'azure_openai_api_key', '')

    print(f"Testing endpoint: {endpoint}")
    print(f"API Key set: {bool(api_key)}\n")

    # Test different deployment names
    deployments = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-35-turbo', 'gpt-5.2']

    async with httpx.AsyncClient(timeout=30.0) as client:
        for dep in deployments:
            url = f'{endpoint}openai/deployments/{dep}/chat/completions?api-version=2024-08-01-preview'
            try:
                response = await client.post(
                    url,
                    headers={'Content-Type': 'application/json', 'api-key': api_key},
                    json={'messages': [{'role': 'user', 'content': 'Hi'}], 'max_tokens': 5}
                )
                if response.status_code == 200:
                    print(f'{dep}: ✅ Available')
                elif response.status_code == 404:
                    print(f'{dep}: ❌ Not deployed')
                else:
                    print(f'{dep}: ⚠️  Status {response.status_code}')
            except Exception as e:
                print(f'{dep}: ❌ Error - {type(e).__name__}')

if __name__ == '__main__':
    asyncio.run(test_models())
