import json
import time
from urllib import request, parse

BASE = "http://localhost:8001"


def http_post(path: str):
    url = f"{BASE}{path}"
    req = request.Request(url, method="POST")
    with request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get(path: str):
    url = f"{BASE}{path}"
    with request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print("Starting AI engine...")
    try:
        res = http_post("/api/ai/start")
        print("start:", res)
    except Exception as e:
        print("start error:", e)

    print("Polling status for ~15s...")
    start = time.time()
    ok = False
    snap = None
    while time.time() - start < 15:
        try:
            snap = http_get("/api/ai/status")
            print("status is_running=", snap.get("is_running"), "active_strategies=", snap.get("active_strategies"))
            if snap.get("is_running") and isinstance(snap.get("strategies"), dict):
                # check one strategy entry shape if present
                if len(snap["strategies"]) > 0:
                    any_id, s = next(iter(snap["strategies"].items()))
                    if "last_analysis" in s:
                        ok = True
                        break
        except Exception as e:
            print("status error:", e)
        time.sleep(2)

    print("Result:", {"ok": ok})
    if not ok:
        print("Final snapshot:", json.dumps(snap, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
