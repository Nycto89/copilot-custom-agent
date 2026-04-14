"""
Shared XSOAR REST API client for Cortex XSOAR 6.14.

All fetch scripts import this module for connection handling.
Credentials can be provided via:
    1. A .env file in scripts/python/ (loaded automatically via python-dotenv)
    2. Shell environment variables (take precedence over .env)

Required variables:
    XSOAR_URL        - Base URL of the XSOAR server (e.g., https://xsoar.example.com)
    XSOAR_API_KEY    - API key for authentication
    XSOAR_VERIFY_SSL - Optional. Set to "false" to disable SSL verification (default: true)

See scripts/python/.env.example for the expected format.
"""

import os
import sys
import json
from pathlib import Path
import requests
import urllib3
from dotenv import load_dotenv

# Load .env from the same directory as this script, regardless of working directory
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path)


def get_config():
    """Read and validate XSOAR connection settings from environment variables."""
    url = os.environ.get("XSOAR_URL", "").rstrip("/")
    api_key = os.environ.get("XSOAR_API_KEY", "")
    verify_ssl = os.environ.get("XSOAR_VERIFY_SSL", "true").lower() != "false"

    if not url:
        print("ERROR: XSOAR_URL environment variable is not set.", file=sys.stderr)
        print("Set it to your XSOAR server URL, e.g.:", file=sys.stderr)
        print('  export XSOAR_URL="https://xsoar.example.com"', file=sys.stderr)
        sys.exit(1)

    if not api_key:
        print("ERROR: XSOAR_API_KEY environment variable is not set.", file=sys.stderr)
        print("Generate an API key in XSOAR: Settings > Integrations > API Keys", file=sys.stderr)
        sys.exit(1)

    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    return {
        "url": url,
        "api_key": api_key,
        "verify_ssl": verify_ssl,
    }


def get_headers(api_key):
    """Construct the standard XSOAR API request headers."""
    return {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def request(method, endpoint, body=None, params=None):
    """
    Make an authenticated request to the XSOAR REST API.

    Args:
        method:   HTTP method (GET, POST, PUT, DELETE)
        endpoint: API path, e.g. "/playbook/search"
        body:     Optional dict for JSON request body
        params:   Optional dict for query parameters

    Returns:
        Parsed JSON response as a dict/list.

    Raises:
        SystemExit on connection or authentication errors.
    """
    config = get_config()
    url = f"{config['url']}{endpoint}"
    headers = get_headers(config["api_key"])

    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=body,
            params=params,
            verify=config["verify_ssl"],
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Cannot connect to {config['url']}", file=sys.stderr)
        print("Check that XSOAR_URL is correct and the server is reachable.", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.Timeout:
        print(f"ERROR: Request to {url} timed out after 30 seconds.", file=sys.stderr)
        sys.exit(1)

    if response.status_code == 401:
        print("ERROR: Authentication failed (401).", file=sys.stderr)
        print("Check that XSOAR_API_KEY is valid and not expired.", file=sys.stderr)
        sys.exit(1)
    elif response.status_code == 403:
        print("ERROR: Access denied (403).", file=sys.stderr)
        print("The API key may lack permissions for this endpoint.", file=sys.stderr)
        sys.exit(1)
    elif response.status_code == 404:
        print(f"ERROR: Endpoint not found (404): {endpoint}", file=sys.stderr)
        sys.exit(1)
    elif response.status_code >= 400:
        print(f"ERROR: API returned status {response.status_code}", file=sys.stderr)
        print(f"Response: {response.text[:500]}", file=sys.stderr)
        sys.exit(1)

    if not response.text:
        return {}

    return response.json()


def validate_connection():
    """Test the XSOAR connection by hitting a lightweight endpoint."""
    print("Validating XSOAR connection...")
    try:
        result = request("GET", "/user")
        username = result.get("username", "unknown")
        print(f"Connected successfully. Authenticated as: {username}")
        return True
    except SystemExit:
        print("Connection validation failed.", file=sys.stderr)
        return False


def sanitize_filename(name):
    """Convert a display name to a safe filename (lowercase, hyphens, no special chars)."""
    safe = name.lower().strip()
    safe = safe.replace(" ", "-")
    safe = "".join(c for c in safe if c.isalnum() or c in "-_")
    safe = safe.strip("-_")
    return safe or "unnamed"


def save_json(data, output_path):
    """Write data as formatted JSON to the given path, creating directories if needed."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved: {output_path}")
