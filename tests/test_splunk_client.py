"""Tests for Splunk Client and Execution Interface."""

from src.splunk_client import SplunkClient
from src.models import SplunkQuery, ExtractedIncident


def test_splunk_client_mock_fallback():
    client = SplunkClient(auto_fallback_mock=True)
    query = SplunkQuery(
        query_id="test_error_q",
        category="error_search",
        spl='index=main service="payment-service" status=504',
        description="Test query"
    )
    incident = ExtractedIncident(
        title="Test Incident",
        service_name="payment-service",
        trace_ids=["req-test-123"]
    )

    result = client.execute_query(query, incident_context=incident)
    assert result.total_events > 0
    assert len(result.events) > 0
    assert result.execution_time_seconds >= 0.0
    assert result.error is None
