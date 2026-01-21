"""Tests for Content API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class TestListContent:
    """Tests for GET /api/v1/content endpoint."""
    
    def test_list_content_success(self):
        """Test successful content listing."""
        response = client.get("/api/v1/content")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]
        assert "total" in data["data"]
        assert "page" in data["data"]
        assert "limit" in data["data"]
        assert "has_more" in data["data"]
        assert isinstance(data["data"]["items"], list)
        
    def test_list_content_with_pagination(self):
        """Test content listing with pagination parameters."""
        response = client.get("/api/v1/content?page=1&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["page"] == 1
        assert data["data"]["limit"] == 5
        assert len(data["data"]["items"]) <= 5
        
    def test_list_content_page_2(self):
        """Test content listing page 2."""
        response = client.get("/api/v1/content?page=2&limit=3")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["page"] == 2
        assert data["data"]["limit"] == 3
        
    def test_list_content_with_category_filter(self):
        """Test content listing with category filter."""
        response = client.get("/api/v1/content?category=Azure")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        # All items should have Azure in categories
        for item in data["data"]["items"]:
            assert "Azure" in item["categories"]
            
    def test_list_content_invalid_page(self):
        """Test content listing with invalid page number."""
        response = client.get("/api/v1/content?page=0")
        
        assert response.status_code == 422  # Validation error
        
    def test_list_content_invalid_limit(self):
        """Test content listing with invalid limit."""
        response = client.get("/api/v1/content?limit=200")
        
        assert response.status_code == 422  # Validation error (max 100)
        
    def test_list_content_item_structure(self):
        """Test that content items have correct structure."""
        response = client.get("/api/v1/content")
        
        assert response.status_code == 200
        data = response.json()
        
        if data["data"]["items"]:
            item = data["data"]["items"][0]
            
            # Required fields
            assert "id" in item
            assert "title" in item
            assert "description" in item
            assert "content_type" in item
            assert "categories" in item
            
            # Optional fields should be present (even if None)
            assert "level" in item
            assert "duration_minutes" in item
            assert "view_count" in item
            assert "bookmark_count" in item


class TestSearchContent:
    """Tests for GET /api/v1/content/search endpoint."""
    
    def test_search_content_success(self):
        """Test successful content search."""
        response = client.get("/api/v1/content/search?q=Azure")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]
        
    def test_search_content_with_pagination(self):
        """Test content search with pagination."""
        response = client.get("/api/v1/content/search?q=Azure&page=1&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["page"] == 1
        assert data["data"]["limit"] == 5
        
    def test_search_content_no_results(self):
        """Test content search with no matching results."""
        response = client.get("/api/v1/content/search?q=xyznonexistent123")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0
        
    def test_search_content_missing_query(self):
        """Test content search without query parameter."""
        response = client.get("/api/v1/content/search")
        
        assert response.status_code == 422  # Validation error
        
    def test_search_content_empty_query(self):
        """Test content search with empty query."""
        response = client.get("/api/v1/content/search?q=")
        
        assert response.status_code == 422  # min_length=1
        
    def test_search_content_case_insensitive(self):
        """Test that search is case insensitive."""
        response_lower = client.get("/api/v1/content/search?q=azure")
        response_upper = client.get("/api/v1/content/search?q=AZURE")
        
        assert response_lower.status_code == 200
        assert response_upper.status_code == 200
        
        # Both should find content
        data_lower = response_lower.json()
        data_upper = response_upper.json()
        
        assert data_lower["data"]["total"] == data_upper["data"]["total"]
        
    def test_search_by_description(self):
        """Test search finds content by description."""
        response = client.get("/api/v1/content/search?q=containerized")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should find AKS workshop which has "containerized" in description
        assert data["data"]["total"] >= 1
        
    def test_search_by_category(self):
        """Test search finds content by category."""
        response = client.get("/api/v1/content/search?q=Kubernetes")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["total"] >= 1


class TestGetContent:
    """Tests for GET /api/v1/content/{id} endpoint."""
    
    def test_get_content_success(self):
        """Test successful content retrieval by ID."""
        response = client.get("/api/v1/content/1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["id"] == "1"
        assert "title" in data["data"]
        assert "description" in data["data"]
        
    def test_get_content_not_found(self):
        """Test content not found."""
        response = client.get("/api/v1/content/nonexistent-id-12345")
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["success"] is False
        assert "error" in data
        
    def test_get_content_structure(self):
        """Test that retrieved content has correct structure."""
        response = client.get("/api/v1/content/1")
        
        assert response.status_code == 200
        data = response.json()
        item = data["data"]
        
        # Check all expected fields
        assert "id" in item
        assert "title" in item
        assert "description" in item
        assert "content_type" in item
        assert "categories" in item
        assert "level" in item
        assert "duration_minutes" in item
        assert "view_count" in item
        assert "bookmark_count" in item
        
    def test_get_different_content_items(self):
        """Test retrieving different content items."""
        response1 = client.get("/api/v1/content/1")
        response2 = client.get("/api/v1/content/2")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1["data"]["id"] != data2["data"]["id"]
        assert data1["data"]["title"] != data2["data"]["title"]


class TestContentMeta:
    """Tests for content API response metadata."""
    
    def test_content_response_has_meta(self):
        """Test that responses include meta information."""
        response = client.get("/api/v1/content")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "meta" in data
        assert "timestamp" in data["meta"]
        assert "correlationId" in data["meta"]
        
    def test_content_response_has_correlation_id(self):
        """Test that responses include correlation ID."""
        response = client.get(
            "/api/v1/content",
            headers={"X-Correlation-ID": "test-correlation-123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["meta"]["correlationId"] == "test-correlation-123"
