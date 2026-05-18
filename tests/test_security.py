"""test_security.py — Unit + integration tests for path traversal defenses.

Covers:
- _safe_file_url() unit tests (no server needed)
- /api/docs/ path traversal (server required)
- /api/iterations/ path traversal (server required)
- /api/files/ path traversal edge cases (server required)

Usage:
    # Unit tests only (no server):
    pytest tests/test_security.py -v -k "TestSafeFileUrl"

    # Full suite (server must be running):
    pytest tests/test_security.py -v
"""

import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.models import _safe_file_url

SERVER_URL = "http://127.0.0.1:8080"
API = f"{SERVER_URL}/api"


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def server_url():
    return SERVER_URL


@pytest.fixture(scope="module")
def api_url(server_url):
    return f"{server_url}/api"


# ═══════════════════════════════════════════════════════════
# _safe_file_url() unit tests
# ═══════════════════════════════════════════════════════════

class TestSafeFileUrl:
    """Unit tests for _safe_file_url — no server needed."""

    def test_normal_path(self):
        """Project-internal path returns correct /api/files/ URL."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        abs_path = os.path.join(project_root, "web", "static", "js", "utils.js")
        url = _safe_file_url(abs_path)
        assert url.startswith("/api/files/")
        assert "utils.js" in url
        assert ".." not in url

    def test_outside_project(self):
        """Path outside PROJECT_ROOT returns empty string."""
        url = _safe_file_url("C:/Windows/System32/notepad.exe")
        assert url == ""

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert _safe_file_url("") == ""

    def test_none_input(self):
        """None input returns empty string."""
        assert _safe_file_url(None) == ""

    def test_with_dotdot_traversal(self):
        """Path with .. that normalizes outside project returns empty string."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Construct a path that normpath resolves outside the project
        traversal = os.path.join(project_root, "web", "..", "..", "Windows", "System32")
        url = _safe_file_url(traversal)
        assert url == ""

    def test_output_dir(self):
        """Files in output/ directory are accessible."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        abs_path = os.path.join(project_root, "output", "test.glb")
        url = _safe_file_url(abs_path)
        assert url.startswith("/api/files/output/")
        assert "test.glb" in url

    def test_relative_path_resolves_inside(self):
        """Relative path that stays inside project after normpath."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        safe_root = os.path.normpath(project_root)
        # Go one level down then back up — stays inside
        abs_path = os.path.join(project_root, "web", "..", "web", "static")
        norm = os.path.normpath(abs_path)
        assert norm.startswith(safe_root + os.sep)
        url = _safe_file_url(abs_path)
        assert url.startswith("/api/files/")

    def test_non_string_silent_failure(self):
        """Non-string types that fail normpath return empty string."""
        # A type that os.path.normpath can't handle
        url = _safe_file_url(42)
        assert url == ""


# ═══════════════════════════════════════════════════════════
# /api/docs/ path traversal (server required)
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_docs_path_traversal_encoded(api_url):
    """Encoded traversal like ..%2F..%2F gets blocked."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/docs/..%2F..%2Fetc%2Fpasswd")
        assert r.status_code in (400, 403, 404), f"got {r.status_code}"


@pytest.mark.asyncio
async def test_docs_path_traversal_dotdot(api_url):
    """Literal dot-dot in doc_id is blocked."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/docs/../../etc/passwd")
        assert r.status_code in (400, 403, 404), f"got {r.status_code}"


@pytest.mark.asyncio
async def test_docs_backslash_traversal(api_url):
    """Backslash in doc_id is blocked (Windows path separator)."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/docs/..\\..\\Windows\\System32")
        assert r.status_code in (400, 403, 404), f"got {r.status_code}"


# ═══════════════════════════════════════════════════════════
# /api/iterations/ path traversal (server required)
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_iterations_path_traversal_encoded(api_url):
    """Encoded traversal in iter_id gets blocked."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/iterations/..%2F..%2Fetc%2Fpasswd")
        assert r.status_code in (400, 403, 404), f"got {r.status_code}"


@pytest.mark.asyncio
async def test_iterations_path_traversal_dotdot(api_url):
    """Literal dot-dot in iter_id is blocked."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/iterations/../../etc/passwd")
        assert r.status_code in (400, 403, 404), f"got {r.status_code}"


# ═══════════════════════════════════════════════════════════
# /api/files/ path traversal edge cases (server required)
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_files_path_traversal_dotdot_slash(api_url):
    """Literal ../../ in file path is blocked."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/files/../../Windows/notepad.exe")
        assert r.status_code in (400, 403, 404), f"got {r.status_code}"


@pytest.mark.asyncio
async def test_files_path_traversal_backslash(api_url):
    """Backslash traversal in file path is blocked."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/files/..\\..\\Windows\\notepad.exe")
        assert r.status_code in (400, 403, 404), f"got {r.status_code}"


@pytest.mark.asyncio
async def test_files_valid_path_still_works(api_url):
    """Valid file paths still return 200 (not broken by security checks)."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{api_url}/files/web/static/js/utils.js")
        assert r.status_code == 200, f"got {r.status_code}"


# ═══════════════════════════════════════════════════════════
# /api/open-path/ edge cases (server required)
# ═══════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_open_path_null_bytes(api_url):
    """Null bytes in path are handled safely."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{api_url}/open-path", json={
            "path": "test\x00/file.txt", "action": "open"
        })
        # Should not crash — 400 or 403 expected
        assert r.status_code >= 400, f"got {r.status_code}"
