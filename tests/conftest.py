"""conftest.py - pytest fixtures for test_api.py

Provides a pytest-asyncio client fixture so that:
- pytest can inject an httpx.AsyncClient into each async test
- `python tests/test_api.py --start-server` continues to work (it imports test_api
  but never calls the pytest-style functions directly — they are invoked from
  run_all_tests() which passes its own client instance).
"""
import pytest
import pytest_asyncio
import httpx


@pytest_asyncio.fixture
async def client():
    """Async HTTP client pointed at the local dev server."""
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8080/api", timeout=15) as c:
        yield c