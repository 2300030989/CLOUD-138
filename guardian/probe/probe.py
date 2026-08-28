import os
import socket
import time
from datetime import datetime


API_HOST = os.getenv("API_HOST", "kubernetes.default.svc")
API_PORT = int(os.getenv("API_PORT", "443"))
INTERVAL = int(os.getenv("INTERVAL", "5"))


def check_api():
    try:
        start = time.time()

        with socket.create_connection(
            (API_HOST, API_PORT),
            timeout=3
        ):
            elapsed = time.time() - start

        return True, elapsed

    except Exception as e:
        return False, str(e)


print("======================================")
print("      CLOUD-138 EDGE PROBE")
print("======================================")
print()
print(f"API Host : {API_HOST}")
print(f"API Port : {API_PORT}")
print(f"Interval : {INTERVAL} seconds")
print()

while True:

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    healthy, result = check_api()

    if healthy:
        print(
            f"[{timestamp}] "
            f"API_REACHABLE | "
            f"CONNECT_TIME={result:.4f}s"
        )
    else:
        print(
            f"[{timestamp}] "
            f"API_UNREACHABLE | "
            f"ERROR={result}"
        )

    time.sleep(INTERVAL)
