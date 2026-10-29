"""HTTP availability of screen shells; live/browser checks validate real workflows."""

import sys
import urllib.request

base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
routes = [
    "/",
    "/sign-in",
    "/app",
    "/app/datasets",
    "/app/datasets/new",
    "/app/executions",
    "/app/datasets/current",
    "/app/datasets/current/quality",
    "/app/datasets/current/clean",
    "/app/datasets/current/analyze",
    "/app/analyses/current",
    "/app/analyses/current/insights",
    "/app/dashboards/current",
    "/app/datasets/current/ask",
    "/app/analyses/current/export",
    "/app/settings",
]
for route in routes:
    with urllib.request.urlopen(base + route, timeout=20) as response:
        html = response.read().decode()
        assert response.status == 200, route
        assert "DataPilot" in html, route
    print("PASS", route)
print("Screen shells available. Real authenticated flows require the live/browser checks.")
