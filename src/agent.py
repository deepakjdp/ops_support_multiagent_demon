"""Ops Support Multi-Agent Orchestrator."""

import logging
from typing import Optional, Union, Dict, Any, List
from pathlib import Path

from src.models import (
    EmailMessage,
    ExtractedIncident,
    SplunkQuery,
    SplunkQueryResult,
    LogAnalysisSummary,
    OpsIncidentReport
)
from src.email_parser import EmailParser
from src.splunk_query_gen import SplunkQueryGenerator
from src.splunk_client import SplunkClient
from src.log_analyzer import LogAnalyzer
from src.report_generator import ReportGenerator

logger = logging.getLogger("ops_agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class OpsSupportAgent:
    """End-to-end multi-agent pipeline for Ops Support:
    1. Email Alert Ingestion & Entity Extraction
    2. Splunk SPL Query Synthesis
    3. Splunk Query Execution (Local Instance or Mock Fallback)
    4. Log Telemetry Analysis & Root Cause Identification (RCA)
    5. Incident Investigation Report Generation
    """

    def __init__(
        self,
        splunk_host: Optional[str] = None,
        splunk_port: Optional[int] = None,
        splunk_username: Optional[str] = None,
        splunk_password: Optional[str] = None,
        splunk_scheme: Optional[str] = None,
        output_dir: Optional[Path] = None
    ):
        self.email_parser = EmailParser()
        self.query_generator = SplunkQueryGenerator()
        self.splunk_client = SplunkClient(
            host=splunk_host,
            port=splunk_port,
            username=splunk_username,
            password=splunk_password,
            scheme=splunk_scheme
        )
        self.log_analyzer = LogAnalyzer()
        self.report_generator = ReportGenerator(output_dir=output_dir)

    def process_email_alert(
        self,
        email_input: Union[str, Path, Dict[str, Any], EmailMessage]
    ) -> OpsIncidentReport:
        """Processes an incoming ops incident email and runs the entire automated diagnostic pipeline."""
        
        # Step 1: Ingest and Parse Email
        logger.info("📧 [Agent Step 1/5] Ingesting and parsing email alert...")
        if isinstance(email_input, EmailMessage):
            email_msg = email_input
        elif isinstance(email_input, dict):
            email_msg = self.email_parser.parse_json_alert(email_input)
        elif isinstance(email_input, (str, Path)):
            path = Path(email_input)
            if path.exists() and path.is_file():
                email_msg = self.email_parser.load_from_file(path)
            else:
                email_msg = self.email_parser.parse_eml_str(str(email_input))
        else:
            raise ValueError(f"Unsupported email_input format: {type(email_input)}")

        # Step 2: Extract Structured Incident Details
        logger.info("🔍 [Agent Step 2/5] Extracting incident entities (service, status codes, traces, hostnames)...")
        incident: ExtractedIncident = self.email_parser.extract_incident_details(email_msg)
        logger.info(f"    -> Identified Service: '{incident.service_name}', Severity: '{incident.severity}', Trace IDs: {incident.trace_ids}")

        # Step 3: Generate Splunk SPL Queries
        logger.info("⚡ [Agent Step 3/5] Synthesizing targeted Splunk Search Processing Language (SPL) queries...")
        queries: List[SplunkQuery] = self.query_generator.generate_investigation_suite(incident)
        logger.info(f"    -> Generated {len(queries)} SPL queries for investigation.")

        # Step 4: Execute Splunk Queries
        logger.info(f"🔎 [Agent Step 4/5] Executing queries on Splunk (Connected: {self.splunk_client.is_connected})...")
        query_results: List[SplunkQueryResult] = []
        for q in queries:
            logger.info(f"    -> Executing [{q.query_id}]: {q.description}")
            result = self.splunk_client.execute_query(q, incident_context=incident)
            query_results.append(result)
            logger.info(f"       Found {result.total_events} events in {result.execution_time_seconds}s")

        # Step 5: Log Telemetry Analysis & RCA
        logger.info("🧠 [Agent Step 5/5] Correlating telemetry and deducing Root Cause Analysis (RCA)...")
        analysis: LogAnalysisSummary = self.log_analyzer.analyze_results(incident, query_results)
        logger.info(f"    -> Root Cause Hypothesis: {analysis.root_cause_hypothesis}")

        # Step 6: Generate Final Incident Report
        logger.info("📄 Generating Ops Incident Investigation Report...")
        report = self.report_generator.generate_report(incident, queries, analysis)
        logger.info(f"✅ Report generated successfully: {report.report_id}")

        return report
