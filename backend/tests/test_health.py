"""Test health endpoint and error handling."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Tests for /api/v1/health endpoint."""

    def test_health_check_returns_success(self):
        """Health check should return success with healthy status."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "healthy"
        assert "timestamp" in data["meta"]
        assert "correlationId" in data["meta"]

    def test_health_check_includes_correlation_id_header(self):
        """Health check should include X-Correlation-ID in response headers."""
        response = client.get("/api/v1/health")

        assert "X-Correlation-ID" in response.headers

    def test_health_check_uses_provided_correlation_id(self):
        """Health check should use correlation ID from request header if provided."""
        test_correlation_id = "test-correlation-123"
        response = client.get(
            "/api/v1/health",
            headers={"X-Correlation-ID": test_correlation_id},
        )

        assert response.headers["X-Correlation-ID"] == test_correlation_id
        assert response.json()["meta"]["correlationId"] == test_correlation_id


class TestRootEndpoint:
    """Tests for root endpoint."""

    def test_root_returns_api_info(self):
        """Root endpoint should return API info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "docs" in data
        assert "health" in data


class TestErrorHandling:
    """Tests for error handling - Constitution v1.0.0 compliance."""

    def test_not_found_error_format(self):
        """404 errors should follow Constitution error format."""
        response = client.get("/api/v1/nonexistent-endpoint")

        assert response.status_code == 404

        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"
        assert "message" in data["error"]
        assert "meta" in data
        assert "timestamp" in data["meta"]
        assert "correlationId" in data["meta"]

    def test_not_found_includes_correlation_id_header(self):
        """404 errors should include X-Correlation-ID header."""
        response = client.get("/api/v1/nonexistent-endpoint")

        assert "X-Correlation-ID" in response.headers
        assert response.headers["X-Correlation-ID"] == response.json()["meta"]["correlationId"]

    def test_method_not_allowed_error_format(self):
        """405 errors should follow Constitution error format."""
        response = client.post("/api/v1/health")  # POST not allowed on health

        assert response.status_code == 405

        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "METHOD_NOT_ALLOWED"

    def test_validation_error_endpoint(self):
        """Test validation error returns proper format."""
        response = client.get("/api/v1/test/error/validation")

        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert data["error"]["message"] == "Test validation error"
        assert len(data["error"]["details"]) == 2
        assert data["error"]["details"][0]["field"] == "email"
        assert data["error"]["details"][0]["issue"] == "Invalid email format"

    def test_not_found_error_endpoint(self):
        """Test not found error returns proper format."""
        response = client.get("/api/v1/test/error/notfound")

        assert response.status_code == 404

        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"
        assert data["error"]["message"] == "TestResource not found"
