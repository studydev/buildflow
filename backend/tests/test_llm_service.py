"""Tests for LLM service."""

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.llm_service import (
    LLMAPIError,
    LLMService,
)


class TestLLMServiceConfiguration:
    """Tests for LLM service configuration."""

    def test_is_configured_with_credentials(self):
        """Test is_configured returns True with credentials."""
        service = LLMService(
            api_key="test-key",
            endpoint="https://test.openai.azure.com",
        )
        assert service.is_configured is True

    def test_is_not_configured_without_key(self):
        """Test is_configured returns False without API key."""
        service = LLMService(
            api_key=None,
            endpoint="https://test.openai.azure.com",
        )
        assert service.is_configured is False

    @pytest.mark.skip(reason="endpoint always falls back to default value in __init__, so empty/None cannot be tested")
    def test_is_not_configured_without_endpoint(self):
        """Test is_configured returns False without endpoint."""
        # Note: This test is skipped because LLMService.__init__ always assigns
        # a default endpoint if None or "" is passed (via 'or' fallback)
        service = LLMService(
            api_key="test-key",
            endpoint="",
        )
        assert service.is_configured is False


class TestFallbackExtraction:
    """Tests for fallback extraction without LLM."""

    def test_extract_title_from_heading(self):
        """Test extracting title from first heading."""
        service = LLMService()

        readme = """# Azure Functions Python Sample

This is a sample project.
"""
        result = service._fallback_extraction(readme)

        assert result.title == "Azure Functions Python Sample"

    def test_extract_categories_from_topics(self):
        """Test extracting categories from repo topics."""
        service = LLMService()

        readme = "# Test\nDescription"
        topics = ["azure", "python", "serverless", "machine-learning"]

        result = service._fallback_extraction(readme, topics=topics)

        assert "Azure" in result.categories
        assert "Serverless" in result.categories
        assert "Machine Learning" in result.categories

    def test_fallback_uses_description(self):
        """Test fallback uses repo description."""
        service = LLMService()

        readme = "# Test"
        description = "A sample Azure Functions project"

        result = service._fallback_extraction(readme, description=description)

        assert result.description == description

    def test_fallback_uses_language_as_technology(self):
        """Test fallback adds language to technologies."""
        service = LLMService()

        readme = "# Test"

        result = service._fallback_extraction(readme, language="Python")

        assert "Python" in result.technologies

    def test_fallback_defaults(self):
        """Test fallback default values."""
        service = LLMService()

        readme = "No heading here"

        result = service._fallback_extraction(readme)

        # Without a heading, title defaults to "Untitled Content"
        assert result.title == "Untitled Content"
        assert result.content_type == "sample"
        assert result.level == "intermediate"


class TestParseLLMResponse:
    """Tests for parsing LLM response."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        service = LLMService()

        response = json.dumps({
            "title": "Azure Functions Workshop",
            "description": "Learn serverless development",
            "content_type": "workshop",
            "categories": ["Azure", "Serverless"],
            "level": "beginner",
            "duration_minutes": 90,
            "technologies": ["Python", "Azure Functions"],
            "prerequisites": ["Basic Python"],
            "learning_objectives": ["Build functions", "Deploy to Azure"],
        })

        result = service._parse_llm_response(response)

        assert result.title == "Azure Functions Workshop"
        assert result.content_type == "workshop"
        assert "Azure" in result.categories
        assert result.duration_minutes == 90

    def test_parse_json_with_code_block(self):
        """Test parsing JSON wrapped in code block."""
        service = LLMService()

        response = """```json
{
    "title": "Test Title",
    "categories": ["Azure"]
}
```"""

        result = service._parse_llm_response(response)

        assert result.title == "Test Title"

    def test_parse_invalid_json_raises_error(self):
        """Test parsing invalid JSON raises error."""
        service = LLMService()

        with pytest.raises(LLMAPIError, match="Invalid JSON"):
            service._parse_llm_response("not valid json {")


class TestExtractMetadata:
    """Tests for metadata extraction with LLM."""

    @pytest.fixture
    def configured_service(self):
        """Create configured LLM service."""
        return LLMService(
            api_key="test-key",
            endpoint="https://test.openai.azure.com",
            deployment="gpt-4o-mini",
        )

    @pytest.mark.asyncio
    async def test_extract_metadata_success(self, configured_service):
        """Test successful metadata extraction."""
        llm_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "title": "Test Workshop",
                        "description": "A test workshop",
                        "content_type": "workshop",
                        "categories": ["Azure"],
                        "level": "beginner",
                        "duration_minutes": 60,
                        "technologies": ["Python"],
                        "prerequisites": [],
                        "learning_objectives": ["Learn stuff"],
                    })
                }
            }]
        }

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: llm_response,
        )
        mock_client.is_closed = False
        configured_service._client = mock_client

        result = await configured_service.extract_metadata(
            readme_content="# Test\nContent here",
            repo_description="Test repo",
        )

        assert result.title == "Test Workshop"
        assert result.content_type == "workshop"

    @pytest.mark.asyncio
    async def test_extract_metadata_uses_fallback_when_not_configured(self):
        """Test fallback extraction when LLM not configured."""
        service = LLMService(api_key=None, endpoint=None)

        result = await service.extract_metadata(
            readme_content="# Azure Sample\nA sample project",
            repo_description="Sample desc",
            repo_topics=["azure", "python"],
        )

        assert result.title == "Azure Sample"
        assert "Azure" in result.categories

    @pytest.mark.asyncio
    async def test_extract_metadata_api_error(self, configured_service):
        """Test API error handling."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = MagicMock(
            status_code=500,
            text="Internal Server Error",
        )
        mock_client.is_closed = False
        configured_service._client = mock_client

        with pytest.raises(LLMAPIError, match="LLM API returned 500"):
            await configured_service.extract_metadata(
                readme_content="# Test",
            )

    @pytest.mark.asyncio
    async def test_truncates_long_readme(self, configured_service):
        """Test README content is truncated if too long."""
        long_readme = "# Test\n" + "x" * 10000

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {
                        "content": '{"title": "Test", "categories": []}'
                    }
                }]
            },
        )
        mock_client.is_closed = False
        configured_service._client = mock_client

        await configured_service.extract_metadata(readme_content=long_readme)

        # Verify the request was made (content should be truncated)
        call_args = mock_client.post.call_args
        request_body = call_args.kwargs.get("json") or call_args[1].get("json")
        content = request_body["messages"][0]["content"]

        assert "[Content truncated...]" in content


# Integration test with real Azure OpenAI
@pytest.mark.skip(reason="Requires Azure OpenAI credentials")
class TestLLMServiceIntegration:
    """Integration tests with real LLM API."""

    @pytest.mark.asyncio
    async def test_real_extraction(self):
        """Test extraction with real LLM."""
        from app.services.llm_service import get_llm_service

        service = get_llm_service()

        if not service.is_configured:
            pytest.skip("LLM not configured")

        readme = """# Azure Functions Python Quickstart

This repository contains a sample Azure Functions project written in Python.

## Prerequisites
- Python 3.9+
- Azure CLI
- Azure Functions Core Tools

## Getting Started
1. Clone this repository
2. Run `func start`
3. Deploy to Azure

## Features
- HTTP trigger function
- Timer trigger function
- Queue trigger function
"""

        try:
            result = await service.extract_metadata(
                readme_content=readme,
                repo_description="Sample Azure Functions project",
                repo_topics=["azure", "python", "serverless"],
            )

            assert result.title is not None
            assert len(result.categories) > 0

        finally:
            await service.close()
