"""End-to-End Pipeline Tests for Ops Support Agent."""

import tempfile
from pathlib import Path
from src.agent import OpsSupportAgent


def test_end_to_end_pipeline_with_sample_email():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = OpsSupportAgent(output_dir=Path(tmpdir))

        sample_email = Path("data/sample_emails/payment_gateway_504_timeout.eml")
        assert sample_email.exists()

        report = agent.process_email_alert(sample_email)

        assert report is not None
        assert report.report_id.startswith("RPT-")
        assert report.service_name == "payment-service"
        assert len(report.executed_queries) > 0
        assert report.log_analysis is not None
        assert len(report.action_items_and_remediation) > 0
        assert "Payment" in report.incident_title or "504" in report.incident_title

        # Check saved files on disk
        saved_files = list(Path(tmpdir).glob("*.*"))
        assert len(saved_files) >= 2  # md and json reports


def test_end_to_end_pipeline_with_json_alert():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = OpsSupportAgent(output_dir=Path(tmpdir))

        json_alert = Path("data/sample_emails/cart_api_datadog_alert.json")
        assert json_alert.exists()

        report = agent.process_email_alert(json_alert)

        assert report is not None
        assert report.service_name == "cart-api"
        assert report.log_analysis.total_logs_analyzed > 0
