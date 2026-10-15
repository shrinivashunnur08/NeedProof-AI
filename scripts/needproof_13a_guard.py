"""NeedProof 13A release guard (Python 3.12+, standard library only).

Run from repo root: python scripts/needproof_13a_guard.py preflight
                    python scripts/needproof_13a_guard.py smoke
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
ROUTE = "/api/v1/discovery/stores"
PROJECT = "needproof-ai"
REGION = "asia-south1"
SERVICE = "needproof-decision-api"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def preflight() -> None:
    expected = (
        "backend/Dockerfile",
        "backend/.gcloudignore",
        "backend/requirements-cloud.txt",
        "backend/app/cloud_decision_api.py",
        "backend/app/public_places.py",
        "frontend/src/FreeShowcase.tsx",
        "frontend/src/components/RealStoresDiscovery.tsx",
        "frontend/src/lib/storeDiscovery.ts",
        "frontend/src/lib/cloudDecisions.ts",
    )
    missing = [x for x in expected if not (ROOT / x).is_file()]
    if missing:
        fail("Missing project files: " + ", ".join(missing))

    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    if "app.cloud_decision_api:app" not in dockerfile:
        fail("backend/Dockerfile must run app.cloud_decision_api:app (NOT app.main:app).")
    if "requirements-cloud.txt" not in dockerfile:
        fail("backend/Dockerfile is not using the expected cloud-specific requirements.")

    frontend = (ROOT / "frontend/src/lib/storeDiscovery.ts").read_text(encoding="utf-8")
    back = (BACKEND / "app/cloud_decision_api.py").read_text(encoding="utf-8")
    if ROUTE not in frontend or f'@app.post("{ROUTE}")' not in back:
        fail("Discovery route must be present in both frontend and Cloud Run source.")

    # Catch a subtle failure: local venv may install packages absent from the smaller
    # requirements-cloud.txt. Catch it before building/deploying the Cloud Run image.
    source = (BACKEND / "app/public_places.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    requirements = (BACKEND / "requirements-cloud.txt").read_text(encoding="utf-8").lower()
    dependency_checks = {
        "httpx": ("httpx", "httpx>=0.27,<1"),
        "requests": ("requests", "requests>=2.31,<3"),
        "aiohttp": ("aiohttp", "aiohttp>=3.9,<4"),
        "googlemaps": ("googlemaps", "googlemaps>=4.10,<5"),
    }
    missing_deps = [
        proposed
        for module, (package, proposed) in dependency_checks.items()
        if module in imported and not re.search(r"(?m)^\s*" + re.escape(package) + r"(?:\s|[=<>!\[~]|$)", requirements)
    ]
    if missing_deps:
        fail(
            "New backend imports are absent from backend/requirements-cloud.txt. "
            "Add these lines and rerun: " + ", ".join(missing_deps)
        )

    check = (
        "from app.cloud_decision_api import app; "
        "routes={(r.path,m) for r in app.routes for m in getattr(r,'methods',set())}; "
        "assert ('/api/v1/discovery/stores','POST') in routes, routes; "
        "assert ('/api/v1/decision/replan','POST') in routes, routes; "
        "assert ('/api/v1/decision/verification-plan','POST') in routes, routes; "
        "print('PASS: local Cloud Run app registers 13A and both earlier decision routes')"
    )
    subprocess.run([sys.executable, "-c", check], cwd=BACKEND, check=True)
    print("PASS: 13A deployment prerequisites look consistent.")


def http_status(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET", headers={"Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return response.status, response.read(1000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(1000).decode("utf-8", "replace")


def smoke(url: str | None) -> None:
    if not url:
        cmd = [
            "gcloud", "run", "services", "describe", SERVICE,
            "--project", PROJECT, "--region", REGION,
            "--format=value(status.url)",
        ]
        try:
            url = subprocess.check_output(cmd, text=True, stderr=subprocess.PIPE).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            fail(f"Unable to determine existing Cloud Run service URL: {exc}")
    url = url.rstrip("/")
    if not url.startswith("https://"):
        fail(f"Unexpected Cloud Run URL: {url!r}")
    health_status, health_body = http_status(url + "/health")
    print(f"GET {url}/health -> HTTP {health_status}")
    if health_status != 200 or '"status":"ok"' not in health_body.replace(" ", ""):
        fail(f"Expected healthy decision API; got: {health_body[:250]}")
    status, response = http_status(url + ROUTE)
    print(f"GET {url}{ROUTE} -> HTTP {status}")
    if status != 405:
        fail(
            "Discovery route not found as a POST-only endpoint on LIVE Cloud Run. "
            f"Expected 405 for GET, received {status}: {response[:250]}"
        )
    print("PASS: live Cloud Run exposes Chunk 13A discovery endpoint.")
    print("Note: merchant discovery still requires valid Firebase tokens and Places credentials.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["preflight", "smoke"])
    parser.add_argument("--url", help="Override Cloud Run URL for smoke test")
    args = parser.parse_args()
    if args.command == "preflight":
        preflight()
    else:
        smoke(args.url)
