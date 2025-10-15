import asyncio
import json
import time
from urllib import request

WS_URL = "ws://localhost:8001/ws/ai-trading"
STATUS_URL = "http://localhost:8001/api/ai/status"
START_URL = "http://localhost:8001/api/ai/start"

# Requires: pip install websockets
try:
    import websockets  # type: ignore
except Exception as e:
    print("This test requires the 'websockets' package. Install with: pip install websockets")
    raise


async def ensure_started():
    try:
        request.urlopen(START_URL, timeout=5)
    except Exception:
        pass


aSYNC_SECONDS = 30


async def run_test():
    await ensure_started()
    print(f"Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL, ping_interval=None) as ws:
        start = time.time()
        status_count = 0
        activity_count = 0
        while time.time() - start < aSYNC_SECONDS:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                data = json.loads(msg) if isinstance(msg, (str, bytes)) else msg
                mtype = data.get("type")
                if mtype == "ai_status":
                    status_count += 1
                elif mtype == "ai_activity":
                    activity_count += 1
                print(f"[{int(time.time()*1000)}] {mtype}: keys={list(data.keys())}")
            except asyncio.TimeoutError:
                print("Timeout waiting for message (no messages in 10s)")
        print(f"Summary: ai_status={status_count}, ai_activity={activity_count}")


if __name__ == "__main__":
    asyncio.run(run_test())
