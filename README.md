# 🛡️ Ops Support Multi-Agent System (with Self-Healing)

An enterprise-grade, end-to-end multi-agent system designed for automated operational incident response, log telemetry investigation with Splunk, root cause analysis (RCA), automated self-healing remediation, and executive report synthesis.

---

## 🏗️ Multi-Agent Architecture & Sequence Flow

```mermaid
sequenceDiagram
    autonumber
    actor Monitoring as Monitoring / Email Alert
    participant Ingestion as 📧 Email Parser Agent
    participant Extractor as 🔍 Entity Extractor
    participant SPLGen as ⚡ Splunk Query Gen Agent
    participant Splunk as 🔎 Splunk Telemetry Agent
    participant RCA as 🧠 Log Analyzer & RCA Agent
    participant SelfHeal as 🩺 Self-Healing Agent
    participant Reporter as 📄 Report Generator Agent

    Monitoring->>Ingestion: Ingests .eml / JSON webhook / Text Alert
    Ingestion->>Extractor: Parses MIME, headers, & raw payload
    Extractor->>SPLGen: ExtractedIncident (Service, Status, Trace IDs, Hosts)
    SPLGen->>Splunk: Generates 5 targeted SPL Queries
    Splunk->>RCA: Executes searches (Local Splunk :8089 or Mock Engine)
    RCA->>SelfHeal: LogAnalysisSummary (Error Patterns, RCA Hypothesis)
    SelfHeal->>SelfHeal: Selects Playbook, Executes Remediation, Probes Health
    SelfHeal->>Reporter: SelfHealingResult (Status, Post-Error Rate, Rollback Plan)
    Reporter->>Reporter: Compiles Markdown & JSON Incident Investigation Report
    Reporter-->>Monitoring: Archived Report (RPT-INC-XXXX.md / .json)
```

---

## 🤖 Detailed Agent Directory & Task Breakdown

### 1. 📧 Email Alert Ingestion & Parsing Agent
- **Source File**: [`src/email_parser.py`](src/email_parser.py:1)
- **Role**: Serves as the primary operational entrypoint for all inbound incident signals.
- **Inputs**:
  - Raw MIME `.eml` email files
  - JSON alert webhooks (PagerDuty, Datadog, Prometheus, Alertmanager, AWS CloudWatch, ServiceNow)
  - Plain text alert descriptions
- **Core Tasks & Responsibilities**:
  - Decodes multi-part MIME email structures, character sets, and attachment boundaries.
  - Normalizes heterogeneous alert formats into a standardized internal `EmailMessage` model.
  - Preserves full payload fidelity for forensic traceability.
- **Output**: `EmailMessage` schema.

---

### 2. 🔍 Entity & Context Extraction Agent
- **Source File**: [`src/email_parser.py`](src/email_parser.py:155)
- **Role**: NLP and pattern matching specialist that converts unstructured email text into structured incident context.
- **Core Tasks & Responsibilities**:
  - **Service Identification**: Detects microservices (e.g., `payment-service`, `auth-service`, `cart-api`).
  - **Severity Classification**: Maps priority keywords to standard enterprise tiers (`P1 - Critical`, `P2 - High`, `P3 - Moderate`, `P4 - Low`).
  - **Distributed Trace Extraction**: Pinpoints UUIDs, Hex Traces (`trace_id`, `span_id`, `req-id`, `tx-id`).
  - **HTTP Status Code Mapping**: Captures client/server error codes (`504 Gateway Timeout`, `500 Internal Error`, `503 Service Unavailable`, `429 Too Many Requests`).
  - **Infrastructure Discovery**: Discovers affected hostnames, IP addresses, pods, and database endpoints.
  - **Exception Signature Mining**: Extracts stack trace error classes (`SocketTimeoutException`, `PSQLException`, `HikariPool ConnectionTimeout`).
- **Output**: `ExtractedIncident` schema.

---

### 3. ⚡ Splunk SPL Query Synthesis Agent
- **Source File**: [`src/splunk_query_gen.py`](src/splunk_query_gen.py:1)
- **Role**: Observability engineer generating precision Splunk Search Processing Language (SPL) queries.
- **Core Tasks & Responsibilities**:
  - **Query 1 (Primary Error Search)**:
    ```spl
    index=main (service="payment-service" OR sourcetype="*payment*") (status=504 OR status>=500) | head 50 | table _time, host, service, status, endpoint, error_message, _raw
    ```
  - **Query 2 (Distributed Trace ID Deep Dive)**: Correlates all hop logs matching the extracted trace ID across upstream API gateways and downstream workers.
  - **Query 3 (Status Code & Endpoint Aggregation)**: Computes failure rates grouped by API endpoint path.
  - **Query 4 (Infrastructure Failure Distribution)**: Identifies whether errors are localized to a specific host/pod or distributed across the entire fleet.
  - **Query 5 (Exception & Stack Trace Clustering)**: Uses regular expressions (`rex field=_raw`) to group top recurring exception classes.
- **Output**: `List[SplunkQuery]` containing parameterized search commands, time windows (`earliest`, `latest`), and target indices.

---

### 4. 🔎 Splunk Telemetry & Execution Agent
- **Source File**: [`src/splunk_client.py`](src/splunk_client.py:1)
- **Role**: Manages active connection with Splunk Enterprise / Splunk Cloud.
- **Core Tasks & Responsibilities**:
  - Connects to local or remote Splunk management port (`https://localhost:8089`) using `splunk-sdk`.
  - Executes search jobs in `oneshot` export mode and parses JSON event streams.
  - **Intelligent Offline/Test Mode**: Automatically switches to context-aware simulated event generation when Splunk daemon is offline, ensuring full pipeline testability.
- **Output**: `List[SplunkQueryResult]` containing extracted log events, execution latency, and summary metrics.

---

### 5. 🧠 Log Observability & RCA Reasoning Agent
- **Source File**: [`src/log_analyzer.py`](src/log_analyzer.py:1)
- **Role**: Diagnostic reasoning engine that analyzes Splunk telemetry and determines probable root cause.
- **Core Tasks & Responsibilities**:
  - Computes error ratios, failure distributions, and peak TPS impacts.
  - Isolates dominant failure modes:
    - *Downstream Timeout / Backpressure* (`504 Gateway Timeout` + `SocketTimeoutException`)
    - *Database Connection Starvation* (`HikariPool Connection is not available`)
    - *Database Concurrency Deadlocks* (`PSQLException: deadlock detected on ExclusiveLock`)
    - *Memory Pressure & Out of Memory* (`OOMKilled` / `OutOfMemoryError`)
  - Formulates a detailed **Root Cause Hypothesis** and impact statement.
- **Output**: `LogAnalysisSummary` schema.

---

### 6. 🩺 Self-Healing & Automated Remediation Agent
- **Source File**: [`src/self_healing_agent.py`](src/self_healing_agent.py:1)
- **Role**: SRE automation specialist executing pre-approved remediation playbooks and verifying health recovery.
- **Playbook Catalog**:
  | Playbook ID | Trigger / Root Cause | Automated Remediation Action | Rollback Command |
  | :--- | :--- | :--- | :--- |
  | `PLAYBOOK-NET-01` | Downstream Timeout (504 / SocketTimeout) | Activate circuit breaker & throttle client timeout to 10s | Disable circuit breaker |
  | `PLAYBOOK-DB-02` | HikariCP Connection Pool Starvation | Flush connection leases & rolling pod restart | Rollback Kubernetes deployment |
  | `PLAYBOOK-DB-01` | Database Deadlock / ExclusiveLock | Cancel blocking idle transactions (`pg_cancel_backend`) | N/A (Transient Locks) |
  | `PLAYBOOK-K8S-03` | Memory Exhaustion (OOM) | Auto-scale deployment replicas (+50%) & drain overloaded nodes | Restore replica baseline |
  | `PLAYBOOK-GEN-01` | General Service Degradation | Trigger zero-downtime rolling restart of worker pods | Rollout undo deployment |
- **Verification**: Executes post-healing synthetic health checks to verify error rate drops to `0.0%` and status transitions to `VERIFIED_HEALTHY`.
- **Output**: `SelfHealingResult` schema.

---

### 7. 📄 Ops Incident Report Generation Agent
- **Source File**: [`src/report_generator.py`](src/report_generator.py:1)
- **Role**: Documentation specialist synthesizing all forensic artifacts into executive and engineering reports.
- **Core Tasks & Responsibilities**:
  - Compiles comprehensive Markdown (`.md`) and JSON (`.json`) reports.
  - Structures reports into 9 standardized sections:
    1. Incident Overview (Severity, Service, Trace IDs, Endpoints)
    2. Executive Summary
    3. Self-Healing Remediation & Automation Audit
    4. Splunk SPL Queries Generated & Executed
    5. Log Observability & Metrics Findings
    6. Root Cause Analysis (RCA) Hypothesis
    7. Chronological Timeline of Events
    8. Remediation Action Plan & Runbooks
    9. Escalation & Stakeholder Communication
  - Saves reports automatically to [`reports/`](reports/).
- **Output**: `OpsIncidentReport` schema and persistent disk files.

---

### 8. 🎯 Multi-Agent Orchestrator
- **Source File**: [`src/agent.py`](src/agent.py:1)
- **Role**: Master pipeline conductor coordinating task handoffs and state across all 7 specialized agents.

---

## 🚀 Quick Start Guide

### 1. Requirements & Installation
Ensure Python 3.10+ is installed:
```bash
python3 -m pip install -r requirements.txt
```

### 2. Configure Splunk (Optional)
If running a local Splunk instance, update your `.env` configuration (see [`.env.example`](.env.example)):
```bash
SPLUNK_HOST=localhost
SPLUNK_PORT=8089
SPLUNK_USERNAME=admin
SPLUNK_PASSWORD=your_password
SPLUNK_SCHEME=https
SPLUNK_INDEX=main
SPLUNK_VERIFY_SSL=false
```

To test connectivity to your Splunk instance:
```bash
./run.sh --check-splunk
# OR
python3 run.py --check-splunk
```

---

## 🧪 Running & Testing the Pipeline

### Analyze a Specific Alert Email
```bash
./run.sh --file data/sample_emails/payment_gateway_504_timeout.eml
```

### Run All Sample Incident Alerts
```bash
./run.sh --test-all
```

### Interactive Mode (Paste Raw Alert Text into Terminal)
```bash
./run.sh --interactive
```

### Run Full Pytest Test Suite
```bash
python3 -m pytest tests/ -v
```

---

## 📂 Project Structure

```
ops_support_multiagent_demo/
├── README.md                      # Comprehensive system documentation
├── requirements.txt               # Python package dependencies
├── .env.example                   # Splunk connection configuration template
├── config.py                      # Global configuration and environment settings
├── run.py / run.sh                # CLI entry points and runner scripts
├── src/
│   ├── __init__.py
│   ├── models.py                  # Pydantic data schemas for all agents
│   ├── email_parser.py            # Email parsing & entity extraction agents
│   ├── splunk_query_gen.py        # Splunk SPL query generation agent
│   ├── splunk_client.py           # Splunk API client & mock telemetry engine
│   ├── log_analyzer.py            # Log observability & root cause reasoning agent
│   ├── self_healing_agent.py      # Automated remediation playbooks & verification
│   ├── report_generator.py        # Markdown and JSON report compiler agent
│   └── agent.py                   # Master multi-agent workflow orchestrator
├── data/
│   └── sample_emails/             # Sample incident alerts for testing
│       ├── payment_gateway_504_timeout.eml
│       ├── auth_service_db_deadlock.eml
│       └── cart_api_datadog_alert.json
├── reports/                       # Generated incident investigation reports (.md & .json)
└── tests/                         # Unit and integration test suite
    ├── test_email_parser.py
    ├── test_splunk_query_gen.py
    ├── test_splunk_client.py
    ├── test_log_analyzer.py
    ├── test_self_healing_agent.py
    └── test_end_to_end.py
```
