"""Tests for Log Analyzer and RCA module."""

from src.log_analyzer import LogAnalyzer
from src.models import ExtractedIncident, SplunkQuery, SplunkQueryResult


def test_log_analyzer_root_cause_timeout():
    analyzer = LogAnalyzer()
    incident = ExtractedIncident(
        title="Payment Service Timeouts",
        service_name="payment-service",
        severity="P1 - Critical"
    )

    query = SplunkQuery(
        query_id="q1",
        category="error_search",
        spl="search",
        description="search"
    )

    result = SplunkQueryResult(
        query=query,
        total_events=2,
        events=[
            {
                "_raw": "2025-10-15 14:00:00 [ERROR] [payment-service] status=504 message=\"Gateway Timeout: Downstream payment vendor endpoint timed out\"",
                "status": "504",
                "service": "payment-service",
                "host": "prod-pay-01"
            },
            {
                "exception_type": "SocketTimeoutException",
                "occurrences": 150
            }
        ]
    )

    summary = analyzer.analyze_results(incident, [result])
    assert summary.error_count >= 1
    assert "Timeout" in summary.root_cause_hypothesis or "Downstream" in summary.root_cause_hypothesis
    assert "prod-pay-01" in summary.affected_hosts
