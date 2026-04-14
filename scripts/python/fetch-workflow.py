"""
Fetch a playbook and its entire dependency tree from Cortex XSOAR 6.14.

Recursively walks sub-playbooks, then fetches every automation and integration
referenced anywhere in the tree. Cycle-safe. Writes a manifest.json that the
xsoar-workflow-documentation skill consumes to generate linked documentation.

Usage:
    python scripts/python/fetch-workflow.py --name "EDL Update"
    python scripts/python/fetch-workflow.py --id <playbook-id>

Output:
    investigation/playbooks/<name>.json        (one per playbook in tree)
    investigation/automations/<name>.json      (one per referenced automation)
    investigation/integrations/<name>.json     (one per referenced integration, creds stripped)
    investigation/docs/<root>/manifest.json    (inventory + cross-references)
"""

import argparse
import json
import sys
import os
from collections import deque
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xsoar_client

# Mirror fetch-integrations.py credential fields. Kept local rather than imported
# to avoid coupling this script to fetch-integrations internals.
SENSITIVE_FIELDS = {
    "password", "apikey", "api_key", "apiKey", "credentials", "token",
    "secret", "private_key", "privateKey", "passphrase", "cert", "certificate",
    "client_secret", "clientSecret", "auth_token", "authToken",
}


def strip_credentials(data):
    """Recursively remove sensitive fields from integration metadata."""
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
    if isinstance(data, list):
        return [strip_credentials(item) for item in data]
    return data


def try_fetch_playbook_by_name(name):
    """Search for a playbook by name. Returns None if not found (does not exit)."""
    body = {"query": f'name:"{name}"', "page": 0, "size": 5}
    result = xsoar_client.request("POST", "/playbook/search", body=body)
    playbooks = result.get("playbooks", [])
    if not playbooks:
        return None
    for pb in playbooks:
        if pb.get("name", "").lower() == name.lower():
            return pb
    return playbooks[0]


def try_fetch_playbook_by_id(playbook_id):
    result = xsoar_client.request("GET", f"/playbook/{playbook_id}")
    return result or None


def try_fetch_automation(name):
    body = {"query": f'name:"{name}"', "page": 0, "size": 5}
    result = xsoar_client.request("POST", "/automation/search", body=body)
    scripts = result.get("scripts", [])
    if not scripts:
        return None
    for s in scripts:
        if s.get("name", "").lower() == name.lower():
            return s
    return scripts[0]


def try_fetch_integration(name):
    body = {"query": f'name:"{name}"', "page": 0, "size": 5}
    result = xsoar_client.request("POST", "/settings/integration/search", body=body)
    integrations = result.get("configurations", [])
    if not integrations:
        return None
    for integ in integrations:
        if integ.get("name", "").lower() == name.lower():
            return integ
        if integ.get("brand", "").lower() == name.lower():
            return integ
    return integrations[0]


def extract_refs(playbook):
    """Pull sub-playbook names, automation names, and integration brands from a playbook."""
    sub_playbooks = set()
    automations = set()
    integrations = set()

    tasks = playbook.get("tasks", {})
    for task_data in tasks.values():
        task_info = task_data.get("task", {})

        # Sub-playbooks
        if task_data.get("type") == "playbook" or task_info.get("playbookName"):
            pb_name = task_info.get("playbookName") or task_info.get("name")
            if pb_name:
                sub_playbooks.add(pb_name)

        # Automations — scriptName or script, strip brand prefix
        script_name = task_info.get("scriptName") or task_info.get("script")
        if script_name:
            base = script_name.split("|||")[-1] if "|||" in script_name else script_name
            if base and base not in ("Builtin", ""):
                automations.add(base)

        # Integration brands — explicit brand field + scriptName prefix
        brand = task_info.get("brand")
        if brand and brand not in ("Builtin", ""):
            integrations.add(brand)
        if script_name and "|||" in script_name:
            prefix = script_name.split("|||")[0]
            if prefix and prefix not in ("Builtin", ""):
                integrations.add(prefix)

    return sorted(sub_playbooks), sorted(automations), sorted(integrations)


def playbook_output_path(name):
    return os.path.join("investigation", "playbooks", xsoar_client.sanitize_filename(name) + ".json")


def automation_output_path(name):
    return os.path.join("investigation", "automations", xsoar_client.sanitize_filename(name) + ".json")


def integration_output_path(name):
    return os.path.join("investigation", "integrations", xsoar_client.sanitize_filename(name) + ".json")


def crawl(root_playbook):
    """BFS walk from the root playbook. Returns the manifest dict."""
    playbooks_by_id = {}        # id → playbook record for manifest
    automations_seen = {}       # name → set of playbook names using it
    integrations_seen = {}      # brand → set of playbook names using it
    name_to_id = {}             # lowercase name → id (for cycle detection)

    queue = deque([(root_playbook, None)])  # (playbook obj, parent playbook name)

    while queue:
        playbook, parent = queue.popleft()
        pb_id = playbook.get("id", "")
        pb_name = playbook.get("name", "unnamed-playbook")

        if pb_id in playbooks_by_id:
            # Already processed — just record the new parent reference
            if parent and parent not in playbooks_by_id[pb_id]["parents"]:
                playbooks_by_id[pb_id]["parents"].append(parent)
            print(f"  (skip) '{pb_name}' already fetched — cycle or shared sub-playbook")
            continue

        path = playbook_output_path(pb_name)
        xsoar_client.save_json(playbook, path)

        sub_pbs, autos, integs = extract_refs(playbook)

        playbooks_by_id[pb_id] = {
            "id": pb_id,
            "name": pb_name,
            "file": path.replace("\\", "/"),
            "parents": [parent] if parent else [],
            "sub_playbooks": sub_pbs,
            "automations": autos,
            "integrations": integs,
        }
        name_to_id[pb_name.lower()] = pb_id

        for a in autos:
            automations_seen.setdefault(a, set()).add(pb_name)
        for i in integs:
            integrations_seen.setdefault(i, set()).add(pb_name)

        print(f"  Fetched playbook: {pb_name} "
              f"(sub: {len(sub_pbs)}, auto: {len(autos)}, integ: {len(integs)})")

        # Enqueue sub-playbooks not yet seen
        for sp_name in sub_pbs:
            if sp_name.lower() in name_to_id:
                # Record parent even when skipping re-fetch
                existing_id = name_to_id[sp_name.lower()]
                if pb_name not in playbooks_by_id[existing_id]["parents"]:
                    playbooks_by_id[existing_id]["parents"].append(pb_name)
                continue
            sub_pb = try_fetch_playbook_by_name(sp_name)
            if sub_pb is None:
                print(f"  (miss) sub-playbook '{sp_name}' not found — will mark as external")
                continue
            queue.append((sub_pb, pb_name))

    # Fetch all automations
    print(f"\nFetching {len(automations_seen)} automation(s)...")
    automations_manifest = []
    for name in sorted(automations_seen):
        auto = try_fetch_automation(name)
        if auto is None:
            print(f"  (miss) automation '{name}' not found")
            automations_manifest.append({
                "name": name, "file": None,
                "used_by_playbooks": sorted(automations_seen[name]),
                "status": "not_found",
            })
            continue
        path = automation_output_path(auto.get("name") or name)
        xsoar_client.save_json(auto, path)
        automations_manifest.append({
            "name": auto.get("name") or name,
            "file": path.replace("\\", "/"),
            "used_by_playbooks": sorted(automations_seen[name]),
            "status": "fetched",
        })

    # Fetch all integrations (strip creds)
    print(f"\nFetching {len(integrations_seen)} integration(s) (credentials stripped)...")
    integrations_manifest = []
    for brand in sorted(integrations_seen):
        integ = try_fetch_integration(brand)
        if integ is None:
            print(f"  (miss) integration '{brand}' not found")
            integrations_manifest.append({
                "brand": brand, "file": None,
                "used_by_playbooks": sorted(integrations_seen[brand]),
                "status": "not_found",
            })
            continue
        cleaned = strip_credentials(integ)
        path = integration_output_path(cleaned.get("name") or cleaned.get("brand") or brand)
        xsoar_client.save_json(cleaned, path)
        integrations_manifest.append({
            "brand": cleaned.get("brand") or brand,
            "name": cleaned.get("name"),
            "file": path.replace("\\", "/"),
            "used_by_playbooks": sorted(integrations_seen[brand]),
            "status": "fetched",
        })

    return {
        "root": root_playbook.get("name"),
        "root_id": root_playbook.get("id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "playbooks": list(playbooks_by_id.values()),
        "automations": automations_manifest,
        "integrations": integrations_manifest,
        "stats": {
            "playbooks": len(playbooks_by_id),
            "automations": len(automations_manifest),
            "integrations": len(integrations_manifest),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a playbook and its full dependency tree from XSOAR."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", help="Root playbook name")
    group.add_argument("--id", dest="playbook_id", help="Root playbook ID")
    args = parser.parse_args()

    if args.name:
        root = try_fetch_playbook_by_name(args.name)
        if root is None:
            print(f"ERROR: No playbook found with name: {args.name}", file=sys.stderr)
            sys.exit(1)
    else:
        root = try_fetch_playbook_by_id(args.playbook_id)
        if root is None:
            print(f"ERROR: No playbook found with ID: {args.playbook_id}", file=sys.stderr)
            sys.exit(1)

    root_name = root.get("name", "unnamed-playbook")
    print(f"Crawling dependency tree for: {root_name}\n")

    manifest = crawl(root)

    manifest_dir = os.path.join("investigation", "docs", xsoar_client.sanitize_filename(root_name))
    manifest_path = os.path.join(manifest_dir, "manifest.json")
    xsoar_client.save_json(manifest, manifest_path)

    s = manifest["stats"]
    print(f"\n{'=' * 60}")
    print(f"Workflow: {root_name}")
    print(f"  Playbooks:    {s['playbooks']}")
    print(f"  Automations:  {s['automations']}")
    print(f"  Integrations: {s['integrations']}")
    print(f"  Manifest:     {manifest_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
