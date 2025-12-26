#!/usr/bin/env python3
"""
Endpoint Discovery Script for Django Copyright Compliance Platform.

This script enumerates all URL patterns across all apps by reading
the urls.py files directly and generating a summary of endpoints.

Usage:
    uv run python scripts/discover_endpoints.py

Output:
    - Prints summary of all discovered endpoints
    - Generates endpoint inventory by app
"""
from pathlib import Path
import re


def parse_urls_file(file_path):
    """Parse a Django urls.py file and extract URL patterns."""
    content = file_path.read_text()

    # Find all path() calls
    pattern = r'path\(["\']([^"\']+)["\'],\s*(\w+)(?:\.\w+)?[^)]*(?:,\s*name=["\']([^"\']+)["\'])?[^)]*\)'

    endpoints = []
    for match in re.finditer(pattern, content):
        route = match.group(1)
        view = match.group(2)
        name = match.group(3) or "(unnamed)"

        endpoints.append({
            "route": route,
            "view": view,
            "name": name
        })

    return endpoints


def discover_all_endpoints():
    """Discover all endpoints by reading urls.py files."""
    project_root = Path(__file__).parent.parent
    apps_dir = project_root / "src" / "apps"

    apps = ["dashboard", "ingest", "enrichment", "steps", "api"]

    all_endpoints = {}

    for app in apps:
        urls_file = apps_dir / app / "urls.py"
        if urls_file.exists():
            endpoints = parse_urls_file(urls_file)
            all_endpoints[app] = endpoints

    return all_endpoints


def print_summary(endpoints_by_app):
    """Print summary of discovered endpoints."""
    print("\n" + "=" * 80)
    print("DJANGO ENDPOINT INVENTORY")
    print("=" * 80)

    total = 0
    for app, endpoints in endpoints_by_app.items():
        total += len(endpoints)
        print(f"\n{'─' * 80}")
        print(f"APP: {app.upper()} ({len(endpoints)} endpoints)")
        print(f"{'─' * 80}")

        for ep in endpoints:
            print(f"  GET  {ep['route']:50} → {ep['view']:30} ({ep['name']})")

    print("\n" + "=" * 80)
    print(f"TOTAL ENDPOINTS: {total}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    endpoints = discover_all_endpoints()
    print_summary(endpoints)
