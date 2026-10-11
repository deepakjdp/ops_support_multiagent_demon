"""Splunk Client Interface with Local Instance Connection and Context-Aware Mock Fallback."""

import time
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from config import SplunkConfig
from src.models import SplunkQuery, SplunkQueryResult

logger = logging.getLogger("ops_agent.splunk")


class SplunkClient:
    """Handles communication with Splunk Enterprise / Cloud local or remote instances."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        scheme: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
        auto_fallback_mock: Optional[bool] = None
    ):
        self.host = host or SplunkConfig.HOST
        self.port = port or SplunkConfig.PORT
        self.username = username or SplunkConfig.USERNAME
        self.password = password or SplunkConfig.PASSWORD
        self.scheme = scheme or SplunkConfig.SCHEME
        self.verify_ssl = verify_ssl if verify_ssl is not None else SplunkConfig.VERIFY_SSL
        self.auto_fallback_mock = auto_fallback_mock if auto_fallback_mock is not None else SplunkConfig.AUTO_FALLBACK_MOCK
        
        self.service = None
        self.is_connected = False
        self._initialize_connection()

    def _initialize_connection(self):
        """Attempt connection to Splunk instance."""
        try:
            import splunklib.client as client
            self.service = client.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                scheme=self.scheme,
                autologin=True
            )
            # Test ping
            _ = self.service.apps
            self.is_connected = True
            logger.info(f"Connected successfully to Splunk instance at {self.scheme}://{self.host}:{self.port}")
        except Exception as e:
            self.is_connected = False
            self.service = None
            if self.auto_fallback_mock:
                logger.warning(f"Could not connect to live Splunk instance ({e}). Running in simulation/mock fallback mode.")
            else:
                logger.error(f"Failed to connect to Splunk: {e}")

    def execute_query(self, query: SplunkQuery, incident_context: Optional[Any] = None) -> SplunkQueryResult:
        """Executes a Splunk SPL query and returns formatted events and summary statistics."""
        start_time = time.time()

        if self.is_connected and self.service:
            try:
                return self._execute_live_query(query, start_time)
            except Exception as e:
                logger.warning(f"Live Splunk execution failed: {e}. Falling back to simulation if enabled.")
                if not self.auto_fallback_mock:
                    return SplunkQueryResult(
                        query=query,
                        execution_time_seconds=time.time() - start_time,
                        total_events=0,
                        events=[],
                        error=str(e)
                    )

        # Fallback / Simulated Mock Mode
        return self._generate_simulated_results(query, incident_context, start_time)

    def _execute_live_query(self, query: SplunkQuery, start_time: float) -> SplunkQueryResult:
        """Executes search query via splunk-sdk against live Splunk daemon."""
        import splunklib.results as results

        search_query = query.spl
        if not search_query.strip().startswith("search "):
            search_query = f"search {search_query}"

        kwargs_oneshot = {
            "earliest_time": query.earliest,
            "latest_time": query.latest,
            "exec_mode": "oneshot",
            "count": 100
        }

        job = self.service.jobs.create(search_query, **kwargs_oneshot)
        reader = results.JSONResultsReader(job)
        
        events = []
        for result in reader:
            if isinstance(result, dict):
                events.append(dict(result))

        exec_time = time.time() - start_time
        return SplunkQueryResult(
            query=query,
            execution_time_seconds=round(exec_time, 3),
            total_events=len(events),
            events=events,
            stats_summary={"status": "live_splunk_success", "count": len(events)}
        )

    def _generate_simulated_results(self, query: SplunkQuery, incident_context: Optional[Any], start_time: float) -> SplunkQueryResult:
        """Generates contextual simulated logs and stats based on the query category and incident context."""
        time.sleep(0.04)  # Simulate network hop
        exec_time = round(time.time() - start_time, 3)

        service_name = getattr(incident_context, "service_name", "app-service") if incident_context else "app-service"
        trace_ids = getattr(incident_context, "trace_ids", []) if incident_context else []
        trace_id = trace_ids[0] if trace_ids else "req-4f91b72a-92c1"
        hosts = getattr(incident_context, "hostnames", []) if incident_context else []
        host_1 = hosts[0] if len(hosts) > 0 else f"prod-{service_name}-01.internal"
        host_2 = hosts[1] if len(hosts) > 1 else f"prod-{service_name}-02.internal"
        endpoints = getattr(incident_context, "endpoints", []) if incident_context else []
        primary_endpoint = endpoints[0] if endpoints else f"/api/v1/{service_name}/action"

        error_keywords = [str(k).lower() for k in getattr(incident_context, "error_keywords", [])]
        db_details = [str(k).lower() for k in getattr(incident_context, "database_details", [])]
        status_codes = getattr(incident_context, "status_codes", [500])

        is_deadlock = any("deadlock" in k for k in error_keywords + db_details) or "psql" in "".join(error_keywords)
        is_pool = any(k in "".join(error_keywords + db_details) for k in ["hikari", "pool", "exhaust"])
        is_timeout = 504 in status_codes or any("timeout" in k for k in error_keywords) or not (is_deadlock or is_pool)

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        events = []
        stats_summary = {}

        if query.category == "error_search":
            if is_deadlock:
                events = [
                    {
                        "_time": now_iso,
                        "host": host_1,
                        "service": service_name,
                        "status": "500",
                        "endpoint": primary_endpoint,
                        "error_message": "Deadlock detected when acquiring transaction lock",
                        "_raw": f"{now_iso} [ERROR] [{service_name}] [{trace_id}] host={host_1} endpoint={primary_endpoint} status=500 exception=org.postgresql.util.PSQLException message=\"ERROR: deadlock detected - Process 28919 waits for ExclusiveLock on transaction\""
                    },
                    {
                        "_time": now_iso,
                        "host": host_2,
                        "service": service_name,
                        "status": "500",
                        "endpoint": primary_endpoint,
                        "error_message": "Transaction rolled back due to concurrent update conflict",
                        "_raw": f"{now_iso} [FATAL] [{service_name}] [req-deadlock-991] host={host_2} endpoint={primary_endpoint} status=500 exception=org.postgresql.util.PSQLException message=\"ERROR: transaction aborted due to lock acquisition timeout\""
                    }
                ]
                stats_summary = {"error_rate": "12.2%", "deadlocks_detected": 42}
            elif is_pool:
                events = [
                    {
                        "_time": now_iso,
                        "host": host_1,
                        "service": service_name,
                        "status": "500",
                        "endpoint": primary_endpoint,
                        "error_message": "HikariPool-1 - Connection is not available, request timed out after 30002ms.",
                        "_raw": f"{now_iso} [ERROR] [{service_name}] [{trace_id}] host={host_1} endpoint={primary_endpoint} status=500 exception=java.sql.SQLTransientConnectionException message=\"HikariPool-1 - Connection is not available, request timed out after 30002ms.\""
                    },
                    {
                        "_time": now_iso,
                        "host": host_1,
                        "service": service_name,
                        "status": "500",
                        "endpoint": primary_endpoint,
                        "error_message": "Active DB connections reached maximumPoolSize ceiling (100/100)",
                        "_raw": f"{now_iso} [WARN] [{service_name}] [{trace_id}] host={host_1} Connection pool exhausted: active=100 idle=0 waiting=84"
                    }
                ]
                stats_summary = {"error_rate": "22.5%", "connection_pool_active": 100}
            else:
                events = [
                    {
                        "_time": now_iso,
                        "host": host_1,
                        "service": service_name,
                        "status": "504",
                        "endpoint": primary_endpoint,
                        "error_message": "Gateway Timeout: Downstream payment vendor endpoint timed out after 30000ms",
                        "_raw": f"{now_iso} [ERROR] [{service_name}] [{trace_id}] host={host_1} endpoint={primary_endpoint} status=504 message=\"Gateway Timeout: Downstream payment vendor endpoint timed out after 30000ms\""
                    },
                    {
                        "_time": now_iso,
                        "host": host_2,
                        "service": service_name,
                        "status": "503",
                        "endpoint": primary_endpoint,
                        "error_message": "Service Unavailable: Circuit breaker OPEN for target downstream-provider",
                        "_raw": f"{now_iso} [ERROR] [{service_name}] [req-cb-882] host={host_2} endpoint={primary_endpoint} status=503 message=\"Service Unavailable: Circuit breaker OPEN for target downstream-provider\""
                    }
                ]
                stats_summary = {"error_rate": "18.4%", "status_504_count": 285}

        elif query.category == "trace_lookup":
            events = [
                {
                    "_time": now_iso,
                    "service": "api-gateway",
                    "host": "prod-gateway-01",
                    "endpoint": primary_endpoint,
                    "status": "500" if is_deadlock or is_pool else "504",
                    "log_level": "WARN",
                    "message": f"Client request received with trace_id={trace_id}, forwarding to {service_name}",
                    "_raw": f"{now_iso} [INFO] [api-gateway] trace_id={trace_id} Request forward to {service_name}"
                },
                {
                    "_time": now_iso,
                    "service": service_name,
                    "host": host_1,
                    "endpoint": primary_endpoint,
                    "status": "500" if is_deadlock or is_pool else "504",
                    "log_level": "ERROR",
                    "message": f"Operation failure encountered for trace_id={trace_id}",
                    "_raw": f"{now_iso} [ERROR] [{service_name}] trace_id={trace_id} failure while handling {primary_endpoint}"
                }
            ]
            stats_summary = {"trace_id": trace_id, "correlated_hops": 2}

        elif query.category == "status_aggregation":
            err_code = "500" if (is_deadlock or is_pool) else "504"
            events = [
                {"endpoint": primary_endpoint, "status": err_code, "total_requests": 450, "server_errors": 310, "client_errors": 1},
                {"endpoint": "/health", "status": "200", "total_requests": 600, "server_errors": 0, "client_errors": 0}
            ]
            stats_summary = {"total_requests": 1050, "total_server_errors": 310}

        elif query.category == "host_breakdown":
            events = [
                {"host": host_1, "error_count": 220, "distinct_endpoints": 2, "status_codes": ["500" if (is_deadlock or is_pool) else "504"]},
                {"host": host_2, "error_count": 90, "distinct_endpoints": 1, "status_codes": ["500" if (is_deadlock or is_pool) else "504"]}
            ]
            stats_summary = {"top_impacted_host": host_1}

        elif query.category == "exception_analysis":
            if is_deadlock:
                events = [
                    {"exception_type": "PSQLException", "occurrences": 310, "sample_log": f"{now_iso} org.postgresql.util.PSQLException: ERROR: deadlock detected"}
                ]
            elif is_pool:
                events = [
                    {"exception_type": "SQLTransientConnectionException", "occurrences": 290, "sample_log": f"{now_iso} java.sql.SQLTransientConnectionException: HikariPool-1 connection pool exhausted"}
                ]
            else:
                events = [
                    {"exception_type": "SocketTimeoutException", "occurrences": 285, "sample_log": f"{now_iso} java.net.SocketTimeoutException: Read timed out connecting to payment vendor"}
                ]
            stats_summary = {"dominant_exception": events[0]["exception_type"]}

        return SplunkQueryResult(
            query=query,
            execution_time_seconds=exec_time,
            total_events=len(events),
            events=events,
            stats_summary=stats_summary
        )
