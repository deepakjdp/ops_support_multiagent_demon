"""Ops Incident Report Generator Module."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from config import AgentConfig
from src.models import (
    ExtractedIncident,
    SplunkQuery,
    LogAnalysisSummary,
    OpsIncidentReport
)


class ReportGenerator:
    """Generates comprehensive Markdown, JSON, and HTML Ops support incident reports."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or AgentConfig.OUTPUT_REPORT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        incident: ExtractedIncident,
        queries: List[SplunkQuery],
        analysis: LogAnalysisSummary
    ) -> OpsIncidentReport:
        """Synthesizes all incident artifacts into a structured incident report."""
        report_id = f"RPT-{incident.incident_id or 'OPS'}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Synthesize Executive Summary
        exec_summary = (
            f"An operational incident was detected on service **{incident.service_name}** ({incident.environment}) "
            f"via **{incident.alert_source or 'Monitoring Alert'}** with severity level **{incident.severity}**. "
            f"Automated Splunk log analysis analyzed telemetry and confirmed elevated error rates with primary root cause attributed to: "
            f"*{analysis.root_cause_hypothesis}*"
        )

        # Build Timeline
        timeline = [
            f"[{incident.timestamp_str or 'T-60m'}] Incident alert triggered: {incident.title}",
            f"[{now_str}] Ops Support Agent ingested alert and extracted service, status codes, and trace identifiers.",
            f"[{now_str}] Executed {len(queries)} automated Splunk search queries spanning time range ({incident.earliest_time} to {incident.latest_time}).",
            f"[{now_str}] Correlated log signatures: Identified {len(analysis.key_exceptions)} recurring exception classes across {len(analysis.affected_hosts)} hosts.",
            f"[{now_str}] Root cause analysis completed and remediation action plan formulated."
        ]

        # Action Items & Remediation Plan
        action_items = self._formulate_action_items(incident, analysis)

        # Escalation Target
        escalation = f"Tier-2 Engineering ({incident.service_name} On-Call Team) & Database Reliability Engineering"

        # Generate Full Markdown Document
        markdown_text = self._build_markdown_document(
            report_id=report_id,
            now_str=now_str,
            incident=incident,
            queries=queries,
            analysis=analysis,
            exec_summary=exec_summary,
            timeline=timeline,
            action_items=action_items,
            escalation=escalation
        )

        report = OpsIncidentReport(
            report_id=report_id,
            generated_at=now_str,
            incident_title=incident.title,
            service_name=incident.service_name or "Unknown Service",
            severity=incident.severity,
            status="INVESTIGATED",
            extracted_context=incident,
            executed_queries=queries,
            log_analysis=analysis,
            executive_summary=exec_summary,
            root_cause_analysis=analysis.root_cause_hypothesis,
            timeline_of_events=timeline,
            action_items_and_remediation=action_items,
            recommended_escalation=escalation,
            markdown_content=markdown_text
        )

        # Save to disk
        self._save_reports_to_disk(report)

        return report

    def _formulate_action_items(self, incident: ExtractedIncident, analysis: LogAnalysisSummary) -> List[str]:
        """Generates contextual operational recommendations based on root cause."""
        actions = []
        rca_lower = analysis.root_cause_hypothesis.lower()

        if "timeout" in rca_lower or "504" in rca_lower:
            actions.append("1. **Circuit Breaker & Fallback**: Engage downstream payment provider status page; temporarily activate fallback retry backoff and circuit breaking.")
            actions.append("2. **Connection Timeout Tuning**: Adjust client connect timeout from 30s to 10s to prevent worker thread saturation.")
            actions.append("3. **Service Mesh Health**: Verify Envoy/Istio egress proxy connections and DNS resolution latency.")
        elif "deadlock" in rca_lower:
            actions.append("1. **Transaction Isolation**: Review concurrent transaction order and lock sequences in payment/order settlement routines.")
            actions.append("2. **Database Indices**: Ensure foreign keys and lock query predicate columns are properly indexed.")
            actions.append("3. **Retry with Jitter**: Implement exponential jitter retry on transient database serialization failures.")
        elif "connection pool" in rca_lower or "hikaripool" in rca_lower:
            actions.append("1. **Pool Sizing & Leak Detection**: Increase HikariCP `maximumPoolSize` from current baseline and enable `leakDetectionThreshold=20000ms`.")
            actions.append("2. **Kill Orphaned DB Sessions**: Terminate long-running idle-in-transaction connections on primary database.")
            actions.append("3. **Restart Affected Pods**: Perform rolling restart of impacted worker pods to flush connection pool state.")
        elif "memory" in rca_lower or "oom" in rca_lower:
            actions.append("1. **Horizontal Scaling**: Scale deployment replica count by +50% to distribute memory load.")
            actions.append("2. **Increase JVM/Pod Heap Limits**: Increase container memory limit and inspect recent heap dumps for memory leak.")
        else:
            actions.append("1. **Traffic Throttling**: Temporarily enable rate limiting on impacted endpoints.")
            actions.append("2. **Canary / Rolling Rollback**: Check recent CI/CD deployments in the last 2 hours and initiate rollback if correlated.")

        actions.append(f"4. **Notify Stakeholders**: Dispatch incident status update to `#ops-incident-war-room` and update ticket `{incident.incident_id}`.")
        return actions

    def _build_markdown_document(
        self,
        report_id: str,
        now_str: str,
        incident: ExtractedIncident,
        queries: List[SplunkQuery],
        analysis: LogAnalysisSummary,
        exec_summary: str,
        timeline: List[str],
        action_items: List[str],
        escalation: str
    ) -> str:
        """Constructs a structured Markdown document."""
        md = []
        md.append(f"# 🛡️ Operations Support Incident Investigation Report")
        md.append(f"**Report ID:** `{report_id}` | **Generated:** `{now_str}`")
        md.append(f"**Incident Reference:** `{incident.incident_id}` | **Severity:** `{incident.severity}` | **Status:** `INVESTIGATED`\n")
        md.append("---\n")

        md.append("## 1. 📋 Incident Overview")
        md.append(f"- **Title / Subject:** {incident.title}")
        md.append(f"- **Impacted Service:** `{incident.service_name}` ({incident.environment})")
        md.append(f"- **Alert Source:** {incident.alert_source or 'Email Alert'}")
        md.append(f"- **Detection Timestamp:** {incident.timestamp_str or now_str}")
        if incident.trace_ids:
            md.append(f"- **Extracted Trace / Request IDs:** `{', '.join(incident.trace_ids)}`")
        if incident.endpoints:
            md.append(f"- **Identified Endpoints:** `{', '.join(incident.endpoints)}`")
        if incident.hostnames:
            md.append(f"- **Target Infrastructure:** `{', '.join(incident.hostnames)}`")
        md.append("")

        md.append("## 2. ⚡ Executive Summary")
        md.append(f"{exec_summary}\n")

        md.append("## 3. 🔍 Splunk Queries Generated & Executed")
        for q in queries:
            md.append(f"### 🔹 Query: `{q.query_id}` ({q.category})")
            md.append(f"*{q.description}*")
            md.append(f"```spl\n{q.spl}\n```")
            md.append(f"- **Time Window:** `{q.earliest}` to `{q.latest}` | **Index:** `{q.index}`\n")

        md.append("## 4. 📊 Log Observability & Metrics Findings")
        md.append(f"- **Total Telemetry Events Inspected:** {analysis.total_logs_analyzed}")
        md.append(f"- **Error Event Count:** {analysis.error_count} (Warnings: {analysis.warning_count})")
        md.append(f"- **Impact Assessment:** {analysis.impact_assessment}")
        md.append("")
        
        if analysis.status_code_distribution:
            md.append("#### HTTP Status Code Distribution")
            md.append("| Status Code | Count / Impact |")
            md.append("| :--- | :--- |")
            for code, count in analysis.status_code_distribution.items():
                md.append(f"| **{code}** | {count} |")
            md.append("")

        if analysis.key_exceptions:
            md.append("#### Dominant Exception Signatures")
            for exc in analysis.key_exceptions:
                md.append(f"- 🔴 `{exc}`")
            md.append("")

        if analysis.evidence_logs:
            md.append("#### Key Splunk Evidence Log Snippets")
            md.append("```log")
            for log in analysis.evidence_logs[:5]:
                md.append(log)
            md.append("```\n")

        md.append("## 5. 🎯 Root Cause Analysis (RCA)")
        md.append(f"> **Root Cause Hypothesis:**\n> {analysis.root_cause_hypothesis}\n")

        md.append("## 6. ⏱️ Timeline of Events")
        for t in timeline:
            md.append(f"- {t}")
        md.append("")

        md.append("## 7. 🚀 Remediation Action Plan")
        for act in action_items:
            md.append(f"{act}")
        md.append("")

        md.append("## 8. 📞 Escalation & Communication")
        md.append(f"- **Recommended Escalation Team:** `{escalation}`")
        md.append(f"- **Communication Status:** Triage complete. Investigation report attached for review.\n")

        return "\n".join(md)

    def _save_reports_to_disk(self, report: OpsIncidentReport):
        """Save report as Markdown and JSON on disk."""
        base_name = report.report_id.lower().replace(":", "-")
        md_file = self.output_dir / f"{base_name}.md"
        json_file = self.output_dir / f"{base_name}.json"

        md_file.write_text(report.markdown_content, encoding="utf-8")
        json_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
