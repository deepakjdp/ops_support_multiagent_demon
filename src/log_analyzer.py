"""Log Analyzer and Root Cause Analysis (RCA) Reasoning Module."""

import re
from typing import List, Dict, Any, Set
from collections import Counter, defaultdict

from src.models import ExtractedIncident, SplunkQueryResult, LogAnalysisSummary


class LogAnalyzer:
    """Performs deep log analytics, error clustering, and root cause analysis from Splunk results."""

    def analyze_results(
        self,
        incident: ExtractedIncident,
        query_results: List[SplunkQueryResult]
    ) -> LogAnalysisSummary:
        """Processes Splunk query results and produces an incident diagnosis summary."""
        total_logs = 0
        error_count = 0
        warning_count = 0
        
        status_distribution = Counter()
        affected_hosts: Set[str] = set()
        affected_endpoints: Set[str] = set()
        affected_services: Set[str] = set()
        exceptions_counter = Counter()
        evidence_logs: List[str] = []
        error_signatures = []

        for res in query_results:
            total_logs += res.total_events
            
            for event in res.events:
                raw_log = str(event.get("_raw") or event.get("message") or "")
                
                # Check log level
                if any(lvl in raw_log.upper() for lvl in ["[ERROR]", "[FATAL]", "CRITICAL", "LEVEL=ERROR"]):
                    error_count += 1
                elif any(lvl in raw_log.upper() for lvl in ["[WARN]", "[WARNING]", "LEVEL=WARN"]):
                    warning_count += 1
                else:
                    if event.get("status") and str(event.get("status")).startswith("5"):
                        error_count += 1

                # Extract status
                status = str(event.get("status") or "")
                if status:
                    status_distribution[status] += int(event.get("total_requests") or 1)

                # Extract host
                host = event.get("host")
                if host and str(host) != "None":
                    affected_hosts.add(str(host))

                # Extract endpoint
                endpoint = event.get("endpoint")
                if endpoint:
                    affected_endpoints.add(str(endpoint))

                # Extract service
                service = event.get("service")
                if service:
                    affected_services.add(str(service))

                # Extract exception from structured or raw
                exception_type = event.get("exception_type")
                if exception_type:
                    occurrences = int(event.get("occurrences") or 1)
                    exceptions_counter[exception_type] += occurrences

                # Capture high-value evidence log snippets
                if raw_log and any(k in raw_log.lower() for k in ["timeout", "deadlock", "refused", "exhaust", "504", "500", "503", "oom", "exception"]):
                    if raw_log not in evidence_logs and len(evidence_logs) < 8:
                        evidence_logs.append(raw_log)

        # Merge with incident info if empty
        if incident.service_name:
            affected_services.add(incident.service_name)
        if incident.hostnames:
            affected_hosts.update(incident.hostnames)
        if incident.endpoints:
            affected_endpoints.update(incident.endpoints)

        # Build top error signatures
        for exc, count in exceptions_counter.most_common(5):
            error_signatures.append({"signature": exc, "count": count, "category": "Exception"})

        # Synthesize Root Cause Hypothesis
        root_cause_hypothesis = self._determine_root_cause(incident, exceptions_counter, status_distribution, evidence_logs)

        # Impact Assessment
        impact_assessment = self._assess_impact(status_distribution, affected_endpoints, affected_hosts, error_count)

        return LogAnalysisSummary(
            total_logs_analyzed=max(total_logs, len(evidence_logs)),
            error_count=max(error_count, 1),
            warning_count=warning_count,
            top_error_signatures=error_signatures,
            affected_hosts=list(affected_hosts),
            affected_endpoints=list(affected_endpoints),
            affected_services=list(affected_services),
            status_code_distribution=dict(status_distribution),
            key_exceptions=[f"{k} (x{v})" for k, v in exceptions_counter.most_common(5)],
            root_cause_hypothesis=root_cause_hypothesis,
            evidence_logs=evidence_logs,
            impact_assessment=impact_assessment
        )

    def _determine_root_cause(
        self,
        incident: ExtractedIncident,
        exceptions: Counter,
        status_dist: Counter,
        evidence_logs: List[str]
    ) -> str:
        """Infers probable root cause from correlated findings."""
        top_exceptions = [e[0] for e in exceptions.most_common(3)]
        all_evidence = " ".join(evidence_logs).lower()

        if "sockettimeoutexception" in [e.lower() for e in top_exceptions] or "504" in status_dist or "gateway timeout" in all_evidence or "read timed out" in all_evidence:
            return (
                f"Downstream Dependency Latency/Timeout: The {incident.service_name} experienced upstream/downstream connection timeouts "
                f"(HTTP 504 / SocketTimeoutException), causing request queue backpressure and cascading connection pool exhaustion."
            )
        elif "deadlock" in all_evidence or "psqlexception" in [e.lower() for e in top_exceptions] or "deadlockdetected" in all_evidence:
            return (
                f"Database Transaction Lock Contention: High concurrency transactions on database tables triggered row-level deadlocks, "
                f"causing rolling transaction rollbacks and HTTP 500 errors across active workers."
            )
        elif "sqltransientconnectionexception" in [e.lower() for e in top_exceptions] or "connection pool" in all_evidence or "hikaripool" in all_evidence:
            return (
                f"Database Connection Pool Starvation: Application connection pool (HikariCP/DB Pool) reached maximum capacity and timed out waiting for available connections, "
                f"likely exacerbated by unindexed slow queries holding open leases."
            )
        elif "oomkilled" in all_evidence or "outofmemoryerror" in [e.lower() for e in top_exceptions] or "memory" in all_evidence:
            return (
                f"Memory Exhaustion (OOM): Worker pods exceeded container memory thresholds under peak workload, resulting in SIGKILL/OOM termination and service degradation."
            )
        elif "connection refused" in all_evidence or "broken pipe" in all_evidence:
            return (
                f"Upstream Service Unavailability: Target backend host refused connections on target port. Service instance appears to be down or unreachable via internal service mesh."
            )
        else:
            return (
                f"Service Degradation in {incident.service_name}: Elevated error rates observed with error codes {list(status_dist.keys())}. "
                f"Primary symptoms indicate {', '.join(incident.symptoms[:2]) if incident.symptoms else 'intermittent runtime exceptions'}."
            )

    def _assess_impact(
        self,
        status_dist: Counter,
        endpoints: Set[str],
        hosts: Set[str],
        error_count: int
    ) -> str:
        """Generates a concise operational impact statement."""
        total_errors = sum(v for k, v in status_dist.items() if str(k).startswith(("5", "4"))) or error_count
        endpoints_str = ", ".join(list(endpoints)[:3]) if endpoints else "Core API routes"
        hosts_str = f"{len(hosts)} instance(s)" if hosts else "distributed fleet"

        return (
            f"Impact Scope: Approximately {total_errors}+ failed operations observed across {hosts_str}. "
            f"Critical affected endpoints include: {endpoints_str}. User-facing transactions experienced elevated latency and error responses."
        )
