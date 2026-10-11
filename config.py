"""Configuration settings for the Ops Support Multi-Agent System."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file if available
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class SplunkConfig:
    """Splunk configuration parameters."""
    HOST: str = os.getenv("SPLUNK_HOST", "localhost")
    PORT: int = int(os.getenv("SPLUNK_PORT", "8089"))
    USERNAME: str = os.getenv("SPLUNK_USERNAME", "admin")
    PASSWORD: str = os.getenv("SPLUNK_PASSWORD", "changeme")
    SCHEME: str = os.getenv("SPLUNK_SCHEME", "https")
    DEFAULT_INDEX: str = os.getenv("SPLUNK_INDEX", "main")
    VERIFY_SSL: bool = os.getenv("SPLUNK_VERIFY_SSL", "false").lower() in ("true", "1", "yes")
    AUTO_FALLBACK_MOCK: bool = os.getenv("AUTO_FALLBACK_MOCK_IF_UNREACHABLE", "true").lower() in ("true", "1", "yes")


class AgentConfig:
    """Agent runtime configuration."""
    DEFAULT_TIME_WINDOW_MINUTES: int = int(os.getenv("DEFAULT_TIME_WINDOW_MINUTES", "60"))
    MAX_SPLUNK_RESULTS: int = int(os.getenv("MAX_SPLUNK_RESULTS", "50"))
    OUTPUT_REPORT_DIR: Path = BASE_DIR / "reports"
    SAMPLE_EMAIL_DIR: Path = BASE_DIR / "data" / "sample_emails"


# Ensure directories exist
AgentConfig.OUTPUT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
AgentConfig.SAMPLE_EMAIL_DIR.mkdir(parents=True, exist_ok=True)
