"""conftest.py - pytest configuration and shared fixtures for test suite."""

import sys
import os
from pathlib import Path

# Ensure project root is on path for all tests
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

# Fix Windows console encoding for subprocess output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")