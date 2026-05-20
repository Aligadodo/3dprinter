#!/usr/bin/env python
"""stop-server.py - Terminate the 3D Print Pipeline server on a given port.

Usage:
  python stop-server.py              # stop server on default port 8080
  python stop-server.py --port 9090  # stop server on custom port
"""

import argparse
import os
import subprocess
import sys


def kill_existing(port):
    """Kill any process occupying the target port. Returns True if something was killed."""
    killed = False
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                f'netstat -ano | findstr :{port}', shell=True, text=True
            )
            pids = set()
            for line in out.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 5 and 'LISTENING' in line:
                    pid = parts[-1]
                    if pid != '0':
                        pids.add(pid)
            for pid in pids:
                try:
                    subprocess.run(['taskkill', '/PID', pid, '/F'],
                                   capture_output=True, text=True, timeout=10)
                    print(f"Stopped server (PID {pid}) on port {port}")
                    killed = True
                except Exception as e:
                    print(f"Warning: could not stop PID {pid}: {e}")
        except subprocess.CalledProcessError:
            pass
    else:
        try:
            out = subprocess.check_output(
                ['lsof', '-ti', f':{port}'], text=True, stderr=subprocess.DEVNULL
            )
            pids = [p for p in out.strip().split('\n') if p]
            for pid in pids:
                try:
                    os.kill(int(pid), 9)
                    print(f"Stopped server (PID {pid}) on port {port}")
                    killed = True
                except Exception as e:
                    print(f"Warning: could not stop PID {pid}: {e}")
        except subprocess.CalledProcessError:
            pass

    return killed


def main():
    parser = argparse.ArgumentParser(description="Stop the 3D Print Pipeline server")
    parser.add_argument("--port", type=int, default=8080, help="Port number (default: 8080)")
    args = parser.parse_args()

    print(f"Looking for server on port {args.port}...")
    if kill_existing(args.port):
        print("Done.")
    else:
        print(f"No server found on port {args.port}.")


if __name__ == "__main__":
    main()
