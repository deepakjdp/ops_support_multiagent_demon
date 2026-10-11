# 🛡️ Ops Support Multi-Agent System

An automated Operations Support Agent that:
1. **Reads Ops / Incident Alert Emails** (`.eml`, plain text, JSON webhooks from PagerDuty, Datadog, CloudWatch, etc.).
2. **Extracts Incident Context & Entities** (impacted service, HTTP status codes, trace IDs, hostnames, timestamps, exceptions).
3. **Generates Targeted Splunk Queries (SPL)** (error search, trace ID deep-dive, status aggregation, host failure distribution, exception signatures).
4. **Executes Searches on Local Splunk** (with automatic fallback to mock/simulation mode for offline testing).
5. **Performs Deep Log Observability & RCA** (correlates stack traces, error rates, failure distribution, and deduces root cause hypothesis).
6. **Generates Comprehensive Ops Incident Investigation Reports** (Markdown and JSON formats with actionable remediation steps).

---

## 🏛️ Architecture Overview

```
                                 [ Incoming Alert Email ]
                               (EML / JSON / Webhook / Text)
                                             │
                                             ▼
                                ┌──────────────────────────┐
                                │   Email Parser Agent     │
                                └────────────┬─────────────┘
                                             │ ExtractedIncident
                                             ▼
                                ┌──────────────────────────┐
                                │ Splunk Query Generator   │
                                └────────────┬─────────────┘
                                             │ List[SplunkQuery] (SPL)
                                             ▼
                                ┌──────────────────────────┐
                                │   Splunk Client Engine   │◄── (Local Splunk Instance:8089 / Mock)
                                └────────────┬─────────────┘
                                             │ List[SplunkQueryResult]
                                             ▼
                                ┌──────────────────────────┐
                                │  Log Analyzer & RCA      │
                                └────────────┬─────────────┘
                                             │ LogAnalysisSummary
                                             ▼
                                ┌──────────────────────────┐
                                │ Incident Report Generator│
                                └────────────┬─────────────┘
                                             │
                                 [ Ops Incident Report ]
                                 (Markdown & JSON Artifact)
```

---

## 🚀 Quick Start

### 1. Installation
Install project dependencies:
```bash
pip install -r requirements.txt
```

### 2. Configure Local Splunk (Optional)
If you have a local Splunk instance running, configure your `.env` file (see [`.env.example`](.env.example)):
```bash
SPLUNK_HOST=localhost
SPLUNK_PORT=8089
SPLUNK_USERNAME=admin
SPLUNK_PASSWORD=your_password
SPLUNK_SCHEME=https
SPLUNK_INDEX=main
SPLUNK_VERIFY_SSL=false
```

To test connectivity with your local Splunk instance:
```bash
python run.py --check-splunk
```

---

## 🧪 Usage & Testing

### Run Against a Sample Incident Alert
```bash
python run.py --file data/sample_emails/payment_gateway_504_timeout.eml
```

### Run All Built-in Test Scenarios
```bash
python run.py --test-all
```

### Interactive Mode (Paste Any Email Alert)
```bash
python run.py --interactive
```

### Execute Test Suite
```bash
python -m pytest tests/ -v
```

---

## 📂 Project Structure

- [`config.py`](config.py): Environment and agent configuration.
- [`src/models.py`](src/models.py): Data models and Pydantic schemas.
- [`src/email_parser.py`](src/email_parser.py): Email parsing and entity extraction.
- [`src/splunk_query_gen.py`](src/splunk_query_gen.py): Splunk SPL query generator.
- [`src/splunk_client.py`](src/splunk_client.py): Splunk SDK client with local connection and fallback.
- [`src/log_analyzer.py`](src/log_analyzer.py): Observability analytics and root cause reasoning.
- [`src/report_generator.py`](src/report_generator.py): Markdown & JSON report generator.
- [`src/agent.py`](src/agent.py): Multi-agent workflow orchestrator.
- [`data/sample_emails/`](data/sample_emails/): Sample incident emails (Payment 504, Auth DB Deadlock, Cart DB Starvation).
- [`reports/`](reports/): Output directory for generated incident investigation reports.
- [`run.py`](run.py): CLI interface for running the agent.
