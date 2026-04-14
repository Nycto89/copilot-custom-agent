"""
Fetch integration configuration metadata from Cortex XSOAR 6.14.

Credentials and secrets are stripped from the output before saving.

Usage:
    python scripts/python/fetch-integrations.py --name "Palo Alto Networks PAN-OS"
    python scripts/python/fetch-integrations.py --playbook-name "EDL Update"

Output:
    Saves sanitized integration JSON to investigation/integrations/<name>.json
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xsoar_client

# Fields that may contain credentials — strip these from output
SENSITIVE_FIELDS = {
    "password", "apikey", "api_key", "apiKey", "credentials", "token",
    "secret", "private_key", "privateKey", "passphrase", "cert", "certificate",
    "client_secret", "clientSecret", "auth_token", "authToken",
}


def strip_credentials(data):
    """
    Recursively remove sensitive fields from integration data.
    Also removes any field with 'hidden: true' in the schema.
    """
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if key.lower() in {f.lower() for f in SENSITIVE_FIELDS}:
                cleaned[key] = "[REDACTED]"
            elif isinstance(value, dict) and value.get("hidden"):
                cleaned[key] = "[REDACTED - hidden field]"
            else:
                cleaned[key] = strip_credentials(value)
        return cleaned
    elif isinstance(data, list):
        return [strip_credentials(item) for item in data]
    return data


def fetch_by_name(name):
    """Search for an integration by name."""
    body = {
        "query": f'name:"{name}"',
        "page": 0,
        "size": 5,
    }
    result = xsoar_client.request("POST", "/settings/integration/search", body=body)
    integrations = result.get("configurations", [])

    if not integrations:
        print(f"ERROR: No integration found with name: {name}", file=sys.stderr)
        sys.exit(1)

    for integ in integrations:
        if integ.get("name", "").lower() == name.lower():
            return integ

    # Also check the 'brand' field which often matches the display name
    for integ in integrations:
        if integ.get("brand", "").lower() == name.lower():
            return integ

    print(f"No exact match for '{name}'. Using closest result: '{integrations[0].get('name')}'")
    return integrations[0]


def extract_integrations_from_playbook(playbook_name):
    """Parse a fetched playbook JSON to extract integration brands used."""
    filename = xsoar_client.sanitize_filename(playbook_name) + ".json"
    playbook_path = os.path.join("investigation", "playbooks", filename)

    if not os.path.exists(playbook_path):
        print(f"ERROR: Playbook file not found at {playbook_path}", file=sys.stderr)
        print(f"Fetch it first: python scripts/python/fetch-playbook.py --name \"{playbook_name}\"",
              file=sys.stderr)
        sys.exit(1)

    with open(playbook_path, "r", encoding="utf-8") as f:
        playbook = json.load(f)

    brands = set()
    tasks = playbook.get("tasks", {})
    for task_id, task_data in tasks.items():
        task_info = task_data.get("task", {})
        brand = task_info.get("brand")
        if brand and brand not in ("Builtin", ""):
            brands.add(brand)

        # Also check scriptName for brand prefix (e.g., "PAN-OS|||panorama-get-edl")
        script_name = task_info.get("scriptName", "")
        if "|||" in script_name:
            brand_prefix = script_name.split("|||")[0]
            if brand_prefix and brand_prefix not in ("Builtin", ""):
                brands.add(brand_prefix)

    return sorted(brands)


def save_integration(integration):
    """Sanitize and save a single integration to the investigation directory."""
    cleaned = strip_credentials(integration)
    name = cleaned.get("name") or cleaned.get("brand", "unnamed-integration")
    filename = xsoar_client.sanitize_filename(name) + ".json"
    output_path = os.path.join("investigation", "integrations", filename)
    xsoar_client.save_json(cleaned, output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Fetch XSOAR integration metadata (credentials stripped)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", help="Integration name to search for")
    group.add_argument("--playbook-name", dest="playbook_name",
                       help="Fetch all integrations used by this playbook")
    args = parser.parse_args()

    if args.name:
        integration = fetch_by_name(args.name)
        save_integration(integration)

    elif args.playbook_name:
        brands = extract_integrations_from_playbook(args.playbook_name)
        if not brands:
            print(f"No integrations referenced in playbook '{args.playbook_name}'.")
            return

        print(f"Found {len(brands)} integration(s) referenced in '{args.playbook_name}':")
        for brand in brands:
            print(f"  - {brand}")

        print("\nFetching each integration (credentials will be stripped)...")
        fetched = 0
        failed = []
        for brand in brands:
            try:
                integration = fetch_by_name(brand)
                save_integration(integration)
                fetched += 1
            except SystemExit:
                failed.append(brand)
                print(f"  Skipping '{brand}' (not found or access denied)", file=sys.stderr)

        print(f"\nFetched: {fetched}/{len(brands)}")
        if failed:
            print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
