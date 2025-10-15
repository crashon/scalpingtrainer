import subprocess
import sys
import time
import urllib.request
import json
import os

BASE = "http://127.0.0.1:8001"


def wait_for_health(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(f"{BASE}/healthz", timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    env = os.environ.copy()
    # Start server via uvicorn in a subprocess
    print("[e2e] starting server...")
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001", "--log-level", "warning"], env=env)
    try:
        # Wait for health
        if not wait_for_health(timeout=45):
            print("[e2e] server failed to become healthy in time")
            raise SystemExit(1)
        print("[e2e] server healthy")

        # Run status check script
        print("[e2e] running ai_status_check...")
        rc = subprocess.call([sys.executable, os.path.join("tests", "ai_status_check.py")])
        if rc != 0:
            print(f"[e2e] ai_status_check failed with exit code {rc}")
            raise SystemExit(rc)
        print("[e2e] ai_status_check passed")
    finally:
        print("[e2e] stopping server...")
        try:
            server.terminate()
            # Give it a moment to exit cleanly
            for _ in range(10):
                ret = server.poll()
                if ret is not None:
                    break
                time.sleep(0.5)
            if server.poll() is None:
                server.kill()
        except Exception:
            pass


if __name__ == "__main__":
    main()
