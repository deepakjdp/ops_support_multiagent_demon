"""Tests for Email Parser and Entity Extraction."""

import pytest
from src.email_parser import EmailParser
from src.models import EmailMessage


def test_parse_plain_text():
    text = """Subject: [ALERT] payment-service failure 504
From: pagerduty@ops.local
Date: 2025-10-15T10:00:00Z

We are seeing HTTP 504 gateway timeout on endpoint /api/v1/payments/process with trace_id=req-991203.
Host prod-payment-worker-01 is impacted.
Exception: SocketTimeoutException
"""
    email_msg = EmailParser.parse_eml_str(text)
    assert "payment-service" in email_msg.subject
    
    extracted = EmailParser.extract_incident_details(email_msg)
    assert extracted.service_name == "payment-service"
    assert 504 in extracted.status_codes
    assert "req-991203" in extracted.trace_ids
    assert any("/api/v1/payments/process" in ep for ep in extracted.endpoints)
    assert any("SocketTimeoutException" in kw for kw in extracted.error_keywords)


def test_parse_json_alert():
    json_payload = {
        "alert_name": "High 500 error rate on auth-service",
        "service": "auth-service",
        "severity": "P1 - Critical",
        "description": "500 error spike on /api/v1/auth/token due to PSQLException deadlock on host prod-auth-01.internal",
        "trace_id": "tx-auth-88129"
    }
    email_msg = EmailParser.parse_json_alert(json_payload)
    extracted = EmailParser.extract_incident_details(email_msg)

    assert extracted.service_name == "auth-service"
    assert extracted.severity == "P1 - Critical"
    assert 500 in extracted.status_codes
    assert "tx-auth-88129" in extracted.trace_ids
