#!/usr/bin/env python3
"""
CLI Runner for Ops Support Multi-Agent System.

Usage:
  python run.py --file data/sample_emails/payment_gateway_504_timeout.eml
  python run.py --test-all
  python run.py --check-splunk
  python run.py --interactive
"""

import sys
import argparse
from pathlib import Path

from config import SplunkConfig, AgentConfig
from src.agent import OpsSupportAgent


def check_splunk_connection():
    """Verify connectivity to local or configured Splunk instance."""
    print(f"\n=======================================================")
    print(f"📡 Splunk Instance Connectivity Diagnostic")
    print(f"=======================================================")
    print(f"Target URL : {SplunkConfig.SCHEME}://{SplunkConfig.HOST}:{SplunkConfig.PORT}")
    print(f"Username   : {SplunkConfig.USERNAME}")
    print(f"Index      : {SplunkConfig.DEFAULT_INDEX}")
    print(f"-------------------------------------------------------")

    try:
        import splunklib.client as client
        service = client.connect(
            host=SplunkConfig.HOST,
            port=SplunkConfig.PORT,
            username=SplunkConfig.USERNAME,
            password=SplunkConfig.PASSWORD,
            scheme=SplunkConfig.SCHEME,
            autologin=True
        )
        apps = [app.name for app in service.apps]
        print(f"✅ SUCCESS: Connected to live Splunk instance!")
        print(f"   Available Apps count: {len(apps)}")
        print(f"   Sample apps: {', '.join(apps[:5])}")
        return True
    except Exception as e:
        print(f"⚠️  Live Splunk instance not reachable: {e}")
        print(f"💡 The Ops Support Agent will automatically operate in high-fidelity mock/test mode.")
        return False


def run_single_file(agent: OpsSupportAgent, file_path: Path):
    """Run agent against a single email/alert file."""
    print(f"\n" + "=" * 80)
    print(f"🚀 Processing Alert File: {file_path.name}")
    print("=" * 80)

    report = agent.process_email_alert(file_path)

    print("\n" + "#" * 80)
    print(f"📄 GENERATED INVESTIGATION REPORT: {report.report_id}")
    print("#" * 80)
    print(report.markdown_content)
    print("\n" + "-" * 80)
    print(f"💾 Report saved to directory: {AgentConfig.OUTPUT_REPORT_DIR}")
    print("-" * 80 + "\n")


def run_test_all(agent: OpsSupportAgent):
    """Run all sample alerts in data/sample_emails/."""
    sample_dir = AgentConfig.SAMPLE_EMAIL_DIR
    files = list(sample_dir.glob("*.eml")) + list(sample_dir.glob("*.json"))

    if not files:
        print(f"No sample files found in {sample_dir}")
        return

    print(f"\nFound {len(files)} sample email alerts to test.\n")
    for f in sorted(files):
        run_single_file(agent, f)


def run_interactive(agent: OpsSupportAgent):
    """Interactive mode to paste email content."""
    print("\n📝 Paste email alert text below (press Ctrl+D on empty line when done):\n")
    try:
        content = sys.stdin.read().strip()
        if not content:
            print("No content provided. Exiting.")
            return
        
        report = agent.process_email_alert(content)
        print("\n" + "#" * 80)
        print(report.markdown_content)
        print("#" * 80 + "\n")
    except (KeyboardInterrupt, EOFError):
        print("\nExited.")


def main():
    parser = argparse.ArgumentParser(description="Ops Support Multi-Agent System")
    parser.add_argument("--file", "-f", type=str, help="Path to email file (.eml, .json, .txt)")
    parser.add_argument("--test-all", action="store_true", help="Run all sample incident alert emails")
    parser.add_argument("--check-splunk", action="store_true", help="Check local Splunk instance connectivity")
    parser.add_argument("--interactive", "-i", action="store_true", help="Paste email content interactively")

    args = parser.parse_args()

    if args.check_splunk:
        check_splunk_connection()
        return

    agent = OpsSupportAgent()

    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)
        run_single_file(agent, path)
    elif args.test_all:
        run_test_all(agent)
    elif args.interactive:
        run_interactive(agent)
    else:
        # Default behavior: run against the payment gateway sample alert
        sample_file = AgentConfig.SAMPLE_EMAIL_DIR / "payment_gateway_504_timeout.eml"
        if sample_file.exists():
            run_single_file(agent, sample_file)
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
