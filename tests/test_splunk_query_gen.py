"""Tests for Splunk SPL Query Generator."""

from src.splunk_query_gen import SplunkQueryGenerator
from src.models import ExtractedIncident


def test_generate_investigation_suite():
    incident = ExtractedIncident(
        incident_id="INC-12345",
        title="High error rate on checkout-service",
        service_name="checkout-service",
        severity="P2 - High",
        status_codes=[500, 504],
        trace_ids=["req-trace-9912a"],
        hostnames=["prod-checkout-01.corp.internal"],
        endpoints=["/api/v1/checkout/submit"],
        error_keywords=["TimeoutException"]
    )

    gen = SplunkQueryGenerator(default_index="main")
    queries = gen.generate_investigation_suite(incident)

    assert len(queries) >= 4
    categories = [q.category for q in queries]
    assert "error_search" in categories
    assert "trace_lookup" in categories
    assert "status_aggregation" in categories
    assert "host_breakdown" in categories

    # Check SPL contents
    primary_q = next(q for q in queries if q.category == "error_search")
    assert "checkout-service" in primary_q.spl
    assert "index=main" in primary_q.spl

    trace_q = next(q for q in queries if q.category == "trace_lookup")
    assert "req-trace-9912a" in trace_q.spl
