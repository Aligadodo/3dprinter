#!/usr/bin/env python
"""start-server.py - One-click launcher for the 3D Print Pipeline web UI.

Always stops any existing server on the target port before starting.
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


def kill_existing(port, host="127.0.0.1"):
    """Kill any process occupying the target port. Returns True if something was killed."""
    killed = False
    if sys.platform == "win32":
        try:
            # Use subprocess list form (no shell) and filter in Python
            out = subprocess.check_output(
                ['netstat', '-ano'], text=True
            )
            # Match host:port to avoid killing unrelated processes on same port
            addr_str = f"{host}:{port}" if host != "0.0.0.0" else f":{port}"
            alt_str = f"0.0.0.0:{port}" if host == "127.0.0.1" else ""
            pids = set()
            for line in out.split('\n'):
                line = line.strip()
                if 'LISTENING' not in line:
                    continue
                if addr_str in line or (alt_str and alt_str in line):
                    pass
                else:
                    continue
                parts = line.split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    if pid != '0':
                        pids.add(pid)
            for pid in pids:
                try:
                    subprocess.run(['taskkill', '/PID', pid, '/F'],
                                   capture_output=True, text=True, timeout=10)
                    print(f"  Stopped existing server (PID {pid}) on port {port}")
                    killed = True
                except Exception as e:
                    print(f"  Warning: could not stop PID {pid}: {e}")
        except subprocess.CalledProcessError:
            pass  # No process on that port
    else:
        try:
            out = subprocess.check_output(
                ['lsof', '-ti', f':{port}'], text=True, stderr=subprocess.DEVNULL
            )
            pids = [p for p in out.strip().split('\n') if p]
            for pid in pids:
                try:
                    os.kill(int(pid), 9)
                    print(f"  Stopped existing server (PID {pid}) on port {port}")
                    killed = True
                except Exception as e:
                    print(f"  Warning: could not stop PID {pid}: {e}")
        except subprocess.CalledProcessError:
            pass

    return killed


def check_deps():
    """Check required packages are installed."""
    missing = []
    deps = {
        # Web server
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "python_multipart": "python-multipart",
        "yaml": "PyYAML",
        "httpx": "httpx",
        "markdown": "Markdown",
        "PIL": "Pillow",
        "numpy": "numpy",
        # Mesh processing (relief, repair, simplify, views, boolean, stitch)
        "scipy": "scipy",
        "trimesh": "trimesh",
        "sklearn": "scikit-learn",
        "fast_simplification": "fast_simplification",
        "pymeshfix": "pymeshfix",
        "pyrender": "pyrender",
        "manifold3d": "manifold3d",
        "pymeshlab": "pymeshlab",
        "shapely": "shapely",
        # AI 3D generation (TripoSR)
        "torch": "torch",
        "rembg": "rembg[gpu]",
        "huggingface_hub": "huggingface-hub",
        "omegaconf": "omegaconf",
    }
    for import_name, pip_name in deps.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

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

    # Determine bind address
    if args.host:
        host = args.host
    elif args.lan:
        host = "0.0.0.0"
    else:
        host = "127.0.0.1"

    # Always stop any existing server on the target port first
    print(f"Checking for existing server on port {args.port}...")
    if kill_existing(args.port, host):
        time.sleep(0.5)  # Let the OS release the port
    else:
        print(f"  No existing server found on port {args.port}")

    # Check dependencies first
    print("Checking dependencies...")
    check_deps()
    print("OK\n")

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

    # Launch server (always pass --no-browser since we open browser ourselves above)
    server_script = os.path.join(PROJECT, "web", "server.py")
    cmd = [sys.executable, server_script, "--host", host, "--port", str(args.port), "--no-browser"]

    try:
        subprocess.run(cmd, cwd=PROJECT)
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
