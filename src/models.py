"""Data models and schemas for Ops Support Multi-Agent."""

from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class EmailMessage(BaseModel):
    """Represents an incoming ops alert or incident email."""
    subject: str
    sender: str
    recipient: Optional[str] = None
    date: Optional[str] = None
    body_text: str
    body_html: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    raw_source: Optional[str] = None


class ExtractedIncident(BaseModel):
    """Structured incident details extracted from email content."""
    incident_id: Optional[str] = None
    title: str
    service_name: Optional[str] = None
    environment: str = "production"
    severity: str = "P2 - High"  # P1, P2, P3, P4
    alert_source: Optional[str] = None  # e.g., PagerDuty, Datadog, Prometheus, Dynatrace, Support Team
    timestamp_str: Optional[str] = None
    detected_time: Optional[datetime] = None
    earliest_time: Optional[str] = "-60m"
    latest_time: Optional[str] = "now"
    error_keywords: List[str] = Field(default_factory=list)
    status_codes: List[int] = Field(default_factory=list)
    trace_ids: List[str] = Field(default_factory=list)
    transaction_ids: List[str] = Field(default_factory=list)
    hostnames: List[str] = Field(default_factory=list)
    ip_addresses: List[str] = Field(default_factory=list)
    endpoints: List[str] = Field(default_factory=list)
    database_details: List[str] = Field(default_factory=list)
    symptoms: List[str] = Field(default_factory=list)
    raw_snippets: List[str] = Field(default_factory=list)


class SplunkQuery(BaseModel):
    """A generated Splunk query with metadata."""
    query_id: str
    category: str  # e.g., "error_search", "trace_lookup", "status_aggregation", "host_breakdown"
    spl: str
    description: str
    earliest: str = "-60m"
    latest: str = "now"
    index: str = "main"


class SplunkLogEvent(BaseModel):
    """A single log entry returned from Splunk."""
    model_config = ConfigDict(populate_by_name=True)

    raw: str = Field(alias="_raw", default="")
    time: Optional[str] = Field(alias="_time", default=None)
    host: Optional[str] = None
    source: Optional[str] = None
    sourcetype: Optional[str] = None
    index: Optional[str] = None
    fields: Dict[str, Any] = Field(default_factory=dict)


class SplunkQueryResult(BaseModel):
    """Results from executing a Splunk query."""
    query: SplunkQuery
    execution_time_seconds: float = 0.0
    total_events: int = 0
    events: List[Dict[str, Any]] = Field(default_factory=list)
    stats_summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class LogAnalysisSummary(BaseModel):
    """Summary of log analysis findings."""
    total_logs_analyzed: int = 0
    error_count: int = 0
    warning_count: int = 0
    top_error_signatures: List[Dict[str, Any]] = Field(default_factory=list)
    affected_hosts: List[str] = Field(default_factory=list)
    affected_endpoints: List[str] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    status_code_distribution: Dict[str, int] = Field(default_factory=dict)
    key_exceptions: List[str] = Field(default_factory=list)
    root_cause_hypothesis: str = ""
    evidence_logs: List[str] = Field(default_factory=list)
    impact_assessment: str = ""


class OpsIncidentReport(BaseModel):
    """Final comprehensive Ops support report."""
    report_id: str
    generated_at: str
    incident_title: str
    service_name: str
    severity: str
    status: str = "INVESTIGATED"  # INVESTIGATED, MITIGATED, ESCALATED
    extracted_context: ExtractedIncident
    executed_queries: List[SplunkQuery] = Field(default_factory=list)
    log_analysis: LogAnalysisSummary
    executive_summary: str
    root_cause_analysis: str
    timeline_of_events: List[str] = Field(default_factory=list)
    action_items_and_remediation: List[str] = Field(default_factory=list)
    recommended_escalation: Optional[str] = None
    markdown_content: str = ""
