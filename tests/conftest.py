"""Test setup: load a local .env so the gated live suites (-m live/graph/jira/observability)
pick up credentials from .env, not only shell exports. Offline tests don't read these vars,
so this is harmless for the default run. Shell exports take precedence (override=False)."""

from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:  # python-dotenv is a dev dep; absent in a bare install
    pass
