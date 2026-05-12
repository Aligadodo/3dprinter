"""test_smoke.py — Smoke tests for the 3dprint web frontend.

Validates:
  1. All JS module syntax (no parse errors)
  2. Locale JSON validity and key consistency
  3. Server starts and serves all static file types
  4. Key API endpoints respond
  5. Main page HTML structure is correct

Usage: python web/test_smoke.py          # all checks
       python web/test_smoke.py --quick  # skip server start
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

# Fix Unicode output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(PROJECT_ROOT, "web", "static")
JS_DIR = os.path.join(STATIC_DIR, "js")
LOCALES_DIR = os.path.join(STATIC_DIR, "locales")

passed = 0
failed = 0

def check(description, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {description}")
    else:
        failed += 1
        print(f"  ❌ {description}")
        if detail:
            print(f"     {detail}")

def check_eq(description, actual, expected):
    ok = actual == expected
    check(description, ok, f"expected={expected!r}, got={actual!r}" if not ok else "")

def check_contains(description, haystack, needle):
    ok = needle in haystack
    check(description, ok, f"'{needle}' not found" if not ok else "")


# ─── 1. JS Syntax Check ───
def test_js_syntax():
    print("\n📦 JS Syntax Check")
    js_files = []
    for root, dirs, files in os.walk(JS_DIR):
        for f in files:
            if f.endswith(".js"):
                js_files.append(os.path.join(root, f))

    for fp in sorted(js_files):
        rel = os.path.relpath(fp, PROJECT_ROOT)
        try:
            r = subprocess.run(
                ["node", "--check", fp],
                capture_output=True, text=True, timeout=10
            )
            check(rel, r.returncode == 0, r.stderr.strip())
        except FileNotFoundError:
            check(rel, False, "Node.js not installed — cannot check JS syntax")
            return
        except subprocess.TimeoutExpired:
            check(rel, False, "Timeout")

# ─── 2. Locale JSON Validation ───
def test_locales():
    print("\n🌐 Locale Validation")
    locale_files = [f for f in os.listdir(LOCALES_DIR) if f.endswith(".json")]
    locales = {}
    for lf in sorted(locale_files):
        fp = os.path.join(LOCALES_DIR, lf)
        lang = lf.replace(".json", "")
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                locales[lang] = json.load(fh)
            check(f"{lf} — valid JSON", True)
        except json.JSONDecodeError as e:
            check(f"{lf} — valid JSON", False, str(e))
            continue
        except Exception as e:
            check(f"{lf} — readable", False, str(e))
            continue

    # Key parity check
    if len(locales) >= 2:
        langs = list(locales.keys())
        base = langs[0]
        for other in langs[1:]:
            base_keys = set(_flatten_keys(locales[base]))
            other_keys = set(_flatten_keys(locales[other]))
            missing = base_keys - other_keys
            extra = other_keys - base_keys
            check(f"{base} ↔ {other} key parity",
                  not missing and not extra,
                  f"missing in {other}: {sorted(missing)[:10]} | extra: {sorted(extra)[:10]}" if (missing or extra) else "")

def _flatten_keys(obj, prefix=""):
    keys = []
    for k, v in obj.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict) and not any(isinstance(vv, (dict, list)) for vv in v.values()):
            # Leaf-like object: include its sub-keys
            for sk in v:
                keys.append(f"{full}.{sk}")
        elif isinstance(v, dict):
            keys.extend(_flatten_keys(v, full))
        else:
            keys.append(full)
    return keys


# ─── 3. Server & Static Files ───
def test_server(host="127.0.0.1", port=8080):
    print(f"\n🌐 Server & Static Files (http://{host}:{port})")
    base = f"http://{host}:{port}"

    def fetch(path, expected_status=200):
        try:
            req = urllib.request.Request(f"{base}{path}")
            resp = urllib.request.urlopen(req, timeout=10)
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            content_type = resp.headers.get("Content-Type", "")
            return status, body, content_type
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace"), ""
        except Exception as e:
            return 0, str(e), ""

    # Main page
    status, body, ct = fetch("/")
    check("GET / → 200", status == 200, f"status={status}")
    check_contains("GET / → <main id=\"main\">", body, '<main id="main">')
    check_contains("GET / → <script type=\"module\">", body, 'script type="module"')

    # CSS
    for css in ["/static/css/main.css", "/static/css/components.css",
                "/static/css/workflow.css", "/static/css/pages.css"]:
        status, _, ct = fetch(css)
        check(f"GET {css} → 200", status == 200, f"status={status}")

    # JS
    key_js = [
        "/static/js/app.js",
        "/static/js/router.js",
        "/static/js/i18n.js",
        "/static/js/api.js",
        "/static/js/utils.js",
    ]
    for js in key_js:
        status, body, ct = fetch(js)
        check(f"GET {js} → 200", status == 200, f"status={status}")
        if status == 200:
            # app.js is an entry point with only imports; others use export
            if js.endswith("app.js"):
                check_contains(f"GET {js} — has 'import'", body, "import ")
            else:
                check_contains(f"GET {js} — no syntax error residue", body, "export ")

    # Page modules
    page_js = [
        "dashboard", "new-task", "task-detail", "file-browse",
        "docs", "workflows", "wf-editor", "wf-runner"
    ]
    for pg in page_js:
        status, body, ct = fetch(f"/static/js/pages/{pg}.js")
        check(f"GET /static/js/pages/{pg}.js → 200", status == 200, f"status={status}")

    # Locale JSON
    for lang in ["zh", "en"]:
        status, body, ct = fetch(f"/static/locales/{lang}.json")
        check(f"GET /static/locales/{lang}.json → 200", status == 200, f"status={status}")
        if status == 200:
            try:
                json.loads(body)
                check(f"GET /static/locales/{lang}.json — valid JSON", True)
            except json.JSONDecodeError:
                check(f"GET /static/locales/{lang}.json — valid JSON", False)

    # API endpoints
    status, body, ct = fetch("/api/tasks")
    check("GET /api/tasks → 200", status == 200, f"status={status}")

    status, body, ct = fetch("/api/pipeline-types")
    check("GET /api/pipeline-types → 200", status == 200, f"status={status}")

    status, body, ct = fetch("/api/workflows")
    check("GET /api/workflows → 200", status == 200, f"status={status}")

    status, body, ct = fetch("/api/node-types")
    check("GET /api/node-types → 200", status == 200, f"status={status}")

    # API docs
    status, body, ct = fetch("/docs")
    check("GET /docs → 200", status == 200, f"status={status}")


# ─── Main ───
def main():
    parser = argparse.ArgumentParser(description="3dprint frontend smoke test")
    parser.add_argument("--quick", action="store_true", help="Skip server-dependent tests")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    print("=" * 60)
    print("  3D Print Pipeline — Frontend Smoke Test")
    print("=" * 60)

    test_js_syntax()
    test_locales()

    if not args.quick:
        test_server(port=args.port)

    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed ({passed + failed} total)")
    print(f"{'=' * 60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
