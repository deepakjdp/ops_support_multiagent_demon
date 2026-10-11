"""Email Parser and Incident Details Extraction Module."""

import email
from email import policy
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from src.models import EmailMessage, ExtractedIncident


class EmailParser:
    """Parses incoming ops alert emails (.eml, JSON, plain text) and extracts structured incident entities."""

    # Common regex patterns for ops entities
    UUID_REGEX = re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b')
    HEX_TRACE_REGEX = re.compile(r'\b(?:trace[-_]?id|span[-_]?id|request[-_]?id|req[-_]?id|tx[-_]?id|transaction[-_]?id)[:=\s]+([a-zA-Z0-9_-]{5,64})\b', re.IGNORECASE)
    STATUS_CODE_REGEX = re.compile(r'\b(?:HTTP|status|code|error|returned)?\s*([45]\d{2})\b', re.IGNORECASE)
    IP_REGEX = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
    HOSTNAME_REGEX = re.compile(r'\b(?:[a-zA-Z0-9-]+\.)+(?:internal|corp|net|org|com|local|ec2|compute)\b|\b(?:prod-[a-z0-9-]+|ip-[0-9-]+|pod-[a-z0-9-]+|srv-[a-z0-9-]+|worker-[0-9]+)\b', re.IGNORECASE)
    ENDPOINT_REGEX = re.compile(r'(?:GET|POST|PUT|DELETE|PATCH|HEAD)\s+([/\w\-]+)|(/api/[/\w\-]+|/v\d+/[/\w\-]+|/auth/[/\w\-]+|/payments?/[/\w\-]+|/cart/[/\w\-]+|/orders?/[/\w\-]+|/health)', re.IGNORECASE)
    SERVICE_REGEX = re.compile(r'\b([a-zA-Z0-9_-]+(?:service|svc|api|worker|backend|frontend|gateway|db|database|processor|consumer))\b', re.IGNORECASE)
    
    # Common exception patterns
    EXCEPTION_PATTERNS = [
        re.compile(r'\b([A-Za-z0-9_]+(?:Exception|Error|Fault|Timeout|Deadlock|Failure|Exhaustion))\b', re.IGNORECASE),
        re.compile(r'(Connection refused|Connection timed out|Pool empty|out of memory|OOMKilled|Broken pipe|SocketTimeout)', re.IGNORECASE)
    ]

    # Severity detection mapping with regex word boundaries
    SEVERITY_KEYWORDS = [
        ("P1 - Critical", [r'\bp1\b', r'\bcritical\b', r'\bsev-1\b', r'\bseverity 1\b', r'\boutage\b', r'\bproduction down\b', r'\bemergency\b', r'\bfatal\b']),
        ("P2 - High", [r'\bp2\b', r'\bhigh\b', r'\bsev-2\b', r'\bseverity 2\b', r'\bmajor\b', r'\berror spike\b', r'\bservice degraded\b']),
        ("P3 - Moderate", [r'\bp3\b', r'\bmedium\b', r'\bmoderate\b', r'\bsev-3\b', r'\bseverity 3\b', r'\bwarning\b', r'\bdegraded\b']),
        ("P4 - Low", [r'\bp4\b', r'\blow\b', r'\bsev-4\b', r'\bseverity 4\b', r'\binfo\b', r'\bminor\b'])
    ]

    @classmethod
    def load_from_file(cls, file_path: Union[str, Path]) -> EmailMessage:
        """Load and parse an email from file (.eml, .json, .txt)."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Email file not found: {file_path}")

        content_bytes = path.read_bytes()
        suffix = path.suffix.lower()

        if suffix == ".json":
            data = json.loads(content_bytes.decode("utf-8", errors="replace"))
            return cls.parse_json_alert(data)
        elif suffix in [".eml", ".msg"]:
            return cls.parse_eml_bytes(content_bytes)
        else:
            # Fallback plain text or eml parsing
            content_str = content_bytes.decode("utf-8", errors="replace")
            if "Subject:" in content_str and "From:" in content_str:
                return cls.parse_eml_str(content_str)
            return EmailMessage(
                subject=path.stem.replace("_", " ").title(),
                sender="alert-system@ops.local",
                body_text=content_str,
                raw_source=content_str
            )

    @classmethod
    def parse_eml_bytes(cls, raw_bytes: bytes) -> EmailMessage:
        """Parse raw email bytes (.eml)."""
        msg = email.message_from_bytes(raw_bytes, policy=policy.default)
        return cls._convert_email_message(msg, raw_bytes.decode("utf-8", errors="replace"))

    @classmethod
    def parse_eml_str(cls, raw_str: str) -> EmailMessage:
        """Parse raw email string (.eml)."""
        msg = email.message_from_string(raw_str, policy=policy.default)
        return cls._convert_email_message(msg, raw_str)

    @classmethod
    def parse_json_alert(cls, data: Dict[str, Any]) -> EmailMessage:
        """Parse JSON formatted alert payload."""
        subject = data.get("subject") or data.get("title") or data.get("alert_name") or "Ops Alert"
        sender = data.get("sender") or data.get("from") or data.get("source") or "alert@monitoring.internal"
        recipient = data.get("recipient") or data.get("to") or "ops-team@company.internal"
        date = data.get("date") or data.get("timestamp") or datetime.now(timezone.utc).isoformat()
        
        # Build comprehensive body text from message/description/payload
        body_parts = []
        if "description" in data:
            body_parts.append(str(data["description"]))
        if "message" in data:
            body_parts.append(str(data["message"]))
        if "body" in data:
            body_parts.append(str(data["body"]))
        if "details" in data:
            body_parts.append(json.dumps(data["details"], indent=2))
        
        # Include full JSON representation for deep entity extraction
        full_json_str = json.dumps(data, indent=2)
        if not body_parts:
            body_parts.append(full_json_str)
        else:
            body_parts.append(full_json_str)

        return EmailMessage(
            subject=str(subject),
            sender=str(sender),
            recipient=str(recipient),
            date=str(date),
            body_text="\n\n".join(body_parts),
            headers={k: str(v) for k, v in data.items() if isinstance(v, (str, int, float, bool))},
            raw_source=full_json_str
        )

    @classmethod
    def _convert_email_message(cls, msg: email.message.EmailMessage, raw_source: str) -> EmailMessage:
        """Extract body and headers from email.message.EmailMessage."""
        subject = str(msg.get("subject", "No Subject"))
        sender = str(msg.get("from", "unknown@ops.local"))
        recipient = str(msg.get("to", ""))
        date = str(msg.get("date", ""))

        body_text = ""
        body_html = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                if "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            decoded = payload.decode(charset, errors="replace")
                            if content_type == "text/plain":
                                body_text += decoded + "\n"
                            elif content_type == "text/html":
                                body_html = decoded
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body_text = payload.decode(charset, errors="replace")
                else:
                    body_text = str(msg.get_payload() or "")
            except Exception:
                body_text = str(msg.get_payload() or "")

        headers = {k: str(v) for k, v in msg.items()}

        return EmailMessage(
            subject=subject,
            sender=sender,
            recipient=recipient,
            date=date,
            body_text=body_text.strip() or subject,
            body_html=body_html,
            headers=headers,
            raw_source=raw_source
        )

    @classmethod
    def extract_incident_details(cls, email_msg: EmailMessage) -> ExtractedIncident:
        """Extract structured incident entities and metadata from the parsed email."""
        full_text = f"{email_msg.subject}\n{email_msg.body_text}"
        full_text_lower = full_text.lower()
        
        # 1. Determine severity (prioritizing explicit header if available)
        severity = None
        if "severity" in email_msg.headers:
            header_sev = str(email_msg.headers["severity"]).strip()
            for sev_label, patterns in cls.SEVERITY_KEYWORDS:
                if any(re.search(p, header_sev, re.IGNORECASE) for p in patterns):
                    severity = sev_label
                    break

        if not severity:
            for sev_label, patterns in cls.SEVERITY_KEYWORDS:
                if any(re.search(p, full_text_lower) for p in patterns):
                    severity = sev_label
                    break
        
        if not severity:
            severity = "P2 - High"

        # 2. Extract Service Name
        service_name = None
        if "service" in email_msg.headers:
            service_name = str(email_msg.headers["service"]).strip().lower()

        if not service_name:
            service_matches = cls.SERVICE_REGEX.findall(full_text)
            if service_matches:
                service_name = service_matches[0].lower()
            else:
                subj_words = re.findall(r'[\w\-]+', email_msg.subject)
                for w in subj_words:
                    if any(x in w.lower() for x in ["auth", "pay", "order", "user", "api", "cart", "gateway", "billing", "checkout", "search", "inventory"]):
                        service_name = w.lower()
                        break
        if not service_name:
            service_name = "application-service"

        # 3. Extract Status Codes
        status_codes = []
        raw_codes = cls.STATUS_CODE_REGEX.findall(full_text)
        for code in raw_codes:
            try:
                c = int(code)
                if 400 <= c <= 599 and c not in status_codes:
                    status_codes.append(c)
            except ValueError:
                pass

        # 4. Extract Trace / Transaction IDs
        trace_ids = []
        for match in cls.HEX_TRACE_REGEX.findall(full_text):
            if match and match not in trace_ids:
                trace_ids.append(match)
        for match in cls.UUID_REGEX.findall(full_text):
            if match and match not in trace_ids:
                trace_ids.append(match)

        # Look for explicit ID mentions like tx-123456 or req_abc123 or tx-auth-88129
        custom_ids = re.findall(r'\b(?:tx|txn|req|corr|trace|order)[-_][a-zA-Z0-9_-]{3,40}\b', full_text, re.IGNORECASE)
        for cid in custom_ids:
            if cid not in trace_ids:
                trace_ids.append(cid)

        # Check explicit trace_id in headers/json
        for k, v in email_msg.headers.items():
            if "trace" in k.lower() or "transaction" in k.lower() or "request" in k.lower():
                if v and v not in trace_ids:
                    trace_ids.append(v)

        # 5. Extract Hostnames and IPs
        hostnames = list(set(cls.HOSTNAME_REGEX.findall(full_text)))
        ip_addresses = list(set(cls.IP_REGEX.findall(full_text)))

        # 6. Extract Endpoints / URLs
        endpoints = []
        # Find all URL paths like /api/v1/payments/process or /api/v1/auth/token
        all_paths = re.findall(r'(/[a-zA-Z0-9_\-]+(?:/[a-zA-Z0-9_\-]+)+)', full_text)
        for p in all_paths:
            if p not in endpoints:
                endpoints.append(p)

        # 7. Extract Exceptions / Error keywords
        error_keywords = []
        for pattern in cls.EXCEPTION_PATTERNS:
            for match in pattern.findall(full_text):
                if match and match not in error_keywords:
                    error_keywords.append(match)

        # Search for database specifics
        db_keywords = []
        for db_term in ["postgres", "mysql", "redis", "mongodb", "oracle", "hikari", "deadlock", "connection pool", "statement timeout"]:
            if db_term in full_text_lower:
                db_keywords.append(db_term)

        # 8. Alert Source Detection
        alert_source = "Email Alert"
        for src in ["PagerDuty", "Datadog", "Prometheus", "Dynatrace", "Grafana", "CloudWatch", "ServiceNow", "Sentry"]:
            if src.lower() in full_text_lower:
                alert_source = src
                break

        # 9. Extract Symptoms & Raw Snippets
        symptoms = []
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        for line in lines:
            if any(term in line.lower() for term in ["error", "fail", "timeout", "exception", "degraded", "spike", "down", "500", "504", "502"]):
                if len(line) < 200 and line not in symptoms:
                    symptoms.append(line)
        
        # Incident ID if present (e.g. INC-10293, ALERT-482)
        incident_id_match = re.search(r'\b(INC(?:IDENT)?[-_]?\d+|ALERT[-_]?\d+|PD[-_]?\d+)\b', full_text, re.IGNORECASE)
        incident_id = incident_id_match.group(1).upper() if incident_id_match else f"INC-{int(datetime.now().timestamp()) % 100000}"

        return ExtractedIncident(
            incident_id=incident_id,
            title=email_msg.subject,
            service_name=service_name,
            environment="production" if "prod" in full_text_lower else "staging" if "staging" in full_text_lower else "production",
            severity=severity,
            alert_source=alert_source,
            timestamp_str=email_msg.date or datetime.now(timezone.utc).isoformat(),
            detected_time=datetime.now(timezone.utc),
            earliest_time="-60m",
            latest_time="now",
            error_keywords=error_keywords,
            status_codes=status_codes,
            trace_ids=trace_ids,
            transaction_ids=trace_ids,
            hostnames=hostnames,
            ip_addresses=ip_addresses,
            endpoints=endpoints,
            database_details=db_keywords,
            symptoms=symptoms[:5],
            raw_snippets=[lines[i] for i in range(min(5, len(lines)))]
        )
