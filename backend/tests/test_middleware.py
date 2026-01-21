"""Test correlation ID middleware."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCorrelationIDMiddleware:
    """Tests for CorrelationIDMiddleware."""

    def test_generates_correlation_id_if_not_provided(self):
        """Should generate a UUID correlation ID if none provided."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers

        correlation_id = response.headers["X-Correlation-ID"]
        # Verify it's a valid UUID format (36 chars with hyphens)
        assert len(correlation_id) == 36
        assert correlation_id.count("-") == 4

    def test_uses_provided_correlation_id(self):
        """Should use correlation ID from request header."""
        test_id = "my-custom-correlation-id-12345"
        response = client.get(
            "/api/v1/health",
            headers={"X-Correlation-ID": test_id},
        )

        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == test_id
        assert response.json()["meta"]["correlationId"] == test_id

    def test_correlation_id_in_response_body_matches_header(self):
        """Correlation ID in response body should match response header."""
        response = client.get("/api/v1/health")

        header_id = response.headers["X-Correlation-ID"]
        body_id = response.json()["meta"]["correlationId"]
        assert header_id == body_id

    def test_correlation_id_persists_across_error_responses(self):
        """Correlation ID should be present in error responses too."""
        test_id = "error-correlation-id-xyz"
        response = client.get(
            "/api/v1/nonexistent",
            headers={"X-Correlation-ID": test_id},
        )

        assert response.status_code == 404
        assert response.headers["X-Correlation-ID"] == test_id
        assert response.json()["meta"]["correlationId"] == test_id

    def test_different_requests_get_different_correlation_ids(self):
        """Each request without X-Correlation-ID should get a unique ID."""
        response1 = client.get("/api/v1/health")
        response2 = client.get("/api/v1/health")

        id1 = response1.headers["X-Correlation-ID"]
        id2 = response2.headers["X-Correlation-ID"]
        assert id1 != id2

    def test_logs_include_correlation_id(self):
        """Request logs should include correlation ID."""
        test_id = "log-test-correlation-id"

        with patch("app.core.middleware.logger") as mock_logger:
            response = client.get(
                "/api/v1/health",
                headers={"X-Correlation-ID": test_id},
            )

            assert response.status_code == 200

            # Check that logger.info was called with correlation_id in extra
            calls = mock_logger.info.call_args_list
            assert len(calls) >= 2  # At least start and complete logs

            # Check that correlation_id is in the extra dict
            for call in calls:
                extra = call.kwargs.get("extra", {})
                assert extra.get("correlation_id") == test_id
