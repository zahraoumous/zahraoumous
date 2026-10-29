"""Probe the running Compose stack without third-party Python dependencies."""

import json
import urllib.request

for path, expected in [("/", "DataPilot"), ("/app", "DataPilot")]:
    with urllib.request.urlopen("http://127.0.0.1:3000" + path, timeout=15) as response:
        assert response.status == 200
        assert expected in response.read().decode()
for route, expected_status in [("live", "ok"), ("ready", "ready")]:
    with urllib.request.urlopen("http://127.0.0.1:8000/health/" + route, timeout=20) as response:
        payload = json.load(response)
        assert payload["status"] == expected_status, payload
        if route == "ready":
            assert payload["checks"] == {"postgres": True, "redis": True, "object_store": True}
        assert response.headers["X-Request-ID"]
print("Web routes, API liveness, migrated PostgreSQL, Redis and object storage: OK")
