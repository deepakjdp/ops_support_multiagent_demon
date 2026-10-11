"""Splunk Query (SPL) Generator Module."""

from typing import List
from src.models import ExtractedIncident, SplunkQuery


class SplunkQueryGenerator:
    """Generates targeted Splunk Search Processing Language (SPL) queries from extracted incident details."""

    def __init__(self, default_index: str = "main"):
        self.default_index = default_index

    def generate_investigation_suite(self, incident: ExtractedIncident) -> List[SplunkQuery]:
        """Generates a complete suite of Splunk queries covering triage, trace lookup, aggregation, and host breakdown."""
        queries: List[SplunkQuery] = []

        earliest = incident.earliest_time or "-60m"
        latest = incident.latest_time or "now"
        index = self.default_index

        # 1. Primary Error Search SPL
        queries.append(self._build_primary_error_query(incident, index, earliest, latest))

        # 2. Specific Trace/Transaction ID Lookup SPL (if any found)
        if incident.trace_ids:
            queries.append(self._build_trace_lookup_query(incident, index, earliest, latest))

        # 3. Status Code and Endpoint Aggregation SPL
        queries.append(self._build_status_aggregation_query(incident, index, earliest, latest))

        # 4. Host/Pod Failure Distribution SPL
        queries.append(self._build_host_breakdown_query(incident, index, earliest, latest))

        # 5. Exception / Stack Trace Analysis SPL
        queries.append(self._build_exception_analysis_query(incident, index, earliest, latest))

        return queries

    def _build_primary_error_query(self, incident: ExtractedIncident, index: str, earliest: str, latest: str) -> SplunkQuery:
        """Builds SPL to fetch recent raw error logs matching the service and error keywords."""
        service_filter = f'(service="{incident.service_name}" OR source="*{incident.service_name}*" OR sourcetype="*{incident.service_name}*" OR "{incident.service_name}")' if incident.service_name else ""
        
        # Build conditions
        conditions = []
        if incident.status_codes:
            status_clause = " OR ".join([f'status={c}' for c in incident.status_codes])
            conditions.append(f"({status_clause} OR status>=500)")
        else:
            conditions.append('(status>=500 OR log_level="ERROR" OR log_level="FATAL" OR "ERROR" OR "Exception" OR "timeout")')

        if incident.error_keywords:
            kw_clause = " OR ".join([f'"{kw}"' for kw in incident.error_keywords[:4]])
            conditions.append(f"({kw_clause})")

        cond_str = " AND ".join(conditions)
        filter_parts = [f"index={index}"]
        if service_filter:
            filter_parts.append(service_filter)
        if cond_str:
            filter_parts.append(cond_str)

        base_search = " ".join(filter_parts)
        spl = f"{base_search} | head 50 | table _time, host, service, status, endpoint, error_message, _raw"

        return SplunkQuery(
            query_id="primary_error_search",
            category="error_search",
            spl=spl,
            description=f"Retrieve top 50 recent error events for {incident.service_name or 'target service'}",
            earliest=earliest,
            latest=latest,
            index=index
        )

    def _build_trace_lookup_query(self, incident: ExtractedIncident, index: str, earliest: str, latest: str) -> SplunkQuery:
        """Builds SPL to track logs containing specific trace or transaction IDs."""
        trace_clauses = []
        for tid in incident.trace_ids[:5]:
            trace_clauses.append(f'"{tid}"')
            trace_clauses.append(f'trace_id="{tid}"')
            trace_clauses.append(f'transaction_id="{tid}"')
            trace_clauses.append(f'request_id="{tid}"')

        combined_trace = " OR ".join(trace_clauses)
        spl = f'index={index} ({combined_trace}) | sort _time | table _time, service, host, endpoint, status, log_level, message, _raw'

        return SplunkQuery(
            query_id="trace_id_deep_dive",
            category="trace_lookup",
            spl=spl,
            description=f"Correlate end-to-end transaction logs for trace IDs: {', '.join(incident.trace_ids[:3])}",
            earliest=earliest,
            latest=latest,
            index=index
        )

    def _build_status_aggregation_query(self, incident: ExtractedIncident, index: str, earliest: str, latest: str) -> SplunkQuery:
        """Builds SPL to aggregate HTTP status codes and endpoint request volume."""
        service_filter = f'service="{incident.service_name}" OR "{incident.service_name}"' if incident.service_name else "*"
        spl = f'index={index} ({service_filter}) | stats count as total_requests, count(eval(status>=500)) as server_errors, count(eval(status>=400 AND status<500)) as client_errors by endpoint, status | sort -server_errors, -total_requests'

        return SplunkQuery(
            query_id="status_aggregation",
            category="status_aggregation",
            spl=spl,
            description=f"Aggregate HTTP response status distribution and failure counts per endpoint",
            earliest=earliest,
            latest=latest,
            index=index
        )

    def _build_host_breakdown_query(self, incident: ExtractedIncident, index: str, earliest: str, latest: str) -> SplunkQuery:
        """Builds SPL to check if error rate is isolated to specific hosts, pods, or availability zones."""
        service_filter = f'service="{incident.service_name}" OR "{incident.service_name}"' if incident.service_name else "*"
        spl = f'index={index} ({service_filter}) (status>=500 OR "ERROR" OR "Exception") | stats count as error_count, dc(endpoint) as distinct_endpoints, values(status) as status_codes by host | sort -error_count'

        return SplunkQuery(
            query_id="host_breakdown",
            category="host_breakdown",
            spl=spl,
            description=f"Analyze error concentration across infrastructure hosts and pods",
            earliest=earliest,
            latest=latest,
            index=index
        )

    def _build_exception_analysis_query(self, incident: ExtractedIncident, index: str, earliest: str, latest: str) -> SplunkQuery:
        """Builds SPL to extract top exception types and stack traces."""
        service_filter = f'service="{incident.service_name}" OR "{incident.service_name}"' if incident.service_name else "*"
        spl = f'index={index} ({service_filter}) ("Exception" OR "Error" OR "timeout" OR "refused") | rex field=_raw "(?<exception_type>[A-Za-z0-9_]+Exception|[A-Za-z0-9_]+Error)" | stats count as occurrences, latest(_raw) as sample_log by exception_type | sort -occurrences'

        return SplunkQuery(
            query_id="exception_analysis",
            category="exception_analysis",
            spl=spl,
            description=f"Group and rank top recurring exception signatures and root error types",
            earliest=earliest,
            latest=latest,
            index=index
        )
