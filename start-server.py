#!/usr/bin/env python
"""start-server.py - One-click launcher for the 3D Print Pipeline web UI.

Checks dependencies, auto-detects network, and opens the browser.
Usage:
  python start-server.py              # local only
  python start-server.py --lan        # LAN accessible
  python start-server.py --port 9090  # custom port
"""

import argparse
import os
import subprocess
import sys
import time

PROJECT = os.path.dirname(os.path.abspath(__file__))


def check_deps():
    """Check required packages are installed."""
    missing = []
    for pkg in ("fastapi", "uvicorn", "python_multipart"):
        try:
            __import__(pkg)
        except ImportError:
            pkg_name = pkg.replace("_", "-")
            missing.append(pkg_name)

    if missing:
        print("Missing dependencies:")
        for m in missing:
            print(f"  - {m}")
        print()
        ans = input("Install now? [Y/n] ").strip().lower()
        if ans in ("", "y", "yes"):
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        else:
            print("Please install manually and try again.")
            sys.exit(1)

    # Check that scripts directory exists
    scripts_dir = os.path.join(PROJECT, "scripts")
    if not os.path.isdir(scripts_dir):
        print(f"Error: scripts/ directory not found at {scripts_dir}")
        sys.exit(1)


def get_lan_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return socket.gethostbyname(socket.gethostname())


def main():
    parser = argparse.ArgumentParser(description="3D Print Pipeline Web Launcher")
    parser.add_argument("--lan", action="store_true", help="Make server accessible on LAN")
    parser.add_argument("--port", type=int, default=8080, help="Port number (default: 8080)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    parser.add_argument("--host", default=None, help="Bind address override")
    args = parser.parse_args()

    # Check dependencies first
    print("Checking dependencies...")
    check_deps()
    print("OK\n")

    # Determine bind address
    if args.host:
        host = args.host
    elif args.lan:
        host = "0.0.0.0"
    else:
        host = "127.0.0.1"

    lan_ip = get_lan_ip() if (host == "0.0.0.0" or args.lan) else None

    # Banner
    print("=" * 48)
    print("   3D Print Pipeline — Web Management Platform")
    print("=" * 48)
    print()
    print(f"   Local:    http://127.0.0.1:{args.port}")
    if lan_ip:
        print(f"   LAN:      http://{lan_ip}:{args.port}")
    print(f"   API Docs: http://127.0.0.1:{args.port}/docs")
    print()
    print("   Pipeline types:")
    for name in ("relief", "lithophane", "triposr", "hunyuan", "views", "repair"):
        print(f"     - {name}")
    print()
    print("   Press Ctrl+C to stop the server.")
    print()

    # Open browser
    if not args.no_browser:
        import webbrowser
        time.sleep(1)
        webbrowser.open(f"http://127.0.0.1:{args.port}")

    # Launch server
    server_script = os.path.join(PROJECT, "web", "server.py")
    cmd = [sys.executable, server_script, "--host", host, "--port", str(args.port)]
    if args.no_browser:
        cmd.append("--no-browser")

    try:
        subprocess.run(cmd, cwd=PROJECT)
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
