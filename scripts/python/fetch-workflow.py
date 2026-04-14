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


def try_fetch_automation_by_id(script_id):
    """Fetch an automation by its scriptId. Falls back to name search if id search misses."""
    body = {"query": f'id:"{script_id}"', "page": 0, "size": 5}
    result = xsoar_client.request("POST", "/automation/search", body=body)
    scripts = result.get("scripts", [])
    if scripts:
        for s in scripts:
            if s.get("id") == script_id:
                return s
        return scripts[0]
    # scriptId may actually be a name (legacy playbooks). Fall back.
    return try_fetch_automation(script_id)


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
    """
    Extract sub-playbook references, automation references, and integration brands.

    Sub-playbooks are keyed by playbookId (task names don't always match playbook names).
    Automations are keyed by scriptId. A scriptId containing '|||' indicates an integration
    command (e.g. 'PAN-OS|||panorama-get-edl'), not a standalone automation.

    Returns:
        sub_playbooks: dict of playbook_id -> display name (best effort)
        automations: dict of script_id -> display name
        integrations: dict of brand -> set of commands referenced
    """
    sub_playbooks = {}
    automations = {}
    integrations = {}

    tasks = playbook.get("tasks", {})
    for task_data in tasks.values():
        task_info = task_data.get("task", {})
        task_type = task_data.get("type", "")

        if task_type == "playbook":
            pb_id = task_info.get("playbookId")
            pb_name = task_info.get("playbookName") or task_info.get("name")
            key = pb_id or pb_name
            if key:
                sub_playbooks.setdefault(key, pb_name or pb_id)
            continue

        if task_type == "regular":
            script_id = task_info.get("scriptId") or task_info.get("script") or ""
            script_name = task_info.get("scriptName") or script_id

            if "|||" in script_id:
                brand, _, command = script_id.partition("|||")
                if brand and brand not in ("Builtin", ""):
                    integrations.setdefault(brand, set()).add(command)
            elif script_id and script_id not in ("Builtin", ""):
                automations.setdefault(script_id, script_name)

        # Explicit brand field on any task type
        brand = task_info.get("brand")
        if brand and brand not in ("Builtin", ""):
            integrations.setdefault(brand, set())

    return sub_playbooks, automations, integrations


def playbook_output_path(name):
    return os.path.join("investigation", "playbooks", xsoar_client.sanitize_filename(name) + ".json")


def automation_output_path(name):
    return os.path.join("investigation", "automations", xsoar_client.sanitize_filename(name) + ".json")


def integration_output_path(name):
    return os.path.join("investigation", "integrations", xsoar_client.sanitize_filename(name) + ".json")


def crawl(root_playbook):
    """BFS walk from the root playbook. Returns the manifest dict."""
    playbooks_by_id = {}         # id → playbook record for manifest
    automations_seen = {}        # scriptId → {"name": str, "used_by": set()}
    integrations_seen = {}       # brand → {"used_by": set(), "commands": set()}

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
            "sub_playbooks": [
                {"id": spid, "name": spname} for spid, spname in sub_pbs.items()
            ],
            "automations": [
                {"id": sid, "name": sname} for sid, sname in autos.items()
            ],
            "integrations": [
                {"brand": b, "commands": sorted(cmds)} for b, cmds in integs.items()
            ],
        }

        for script_id, script_name in autos.items():
            entry = automations_seen.setdefault(script_id, {"name": script_name, "used_by": set()})
            entry["used_by"].add(pb_name)
        for brand, cmds in integs.items():
            entry = integrations_seen.setdefault(brand, {"used_by": set(), "commands": set()})
            entry["used_by"].add(pb_name)
            entry["commands"].update(cmds)

        print(f"  Fetched playbook: {pb_name} "
              f"(sub: {len(sub_pbs)}, auto: {len(autos)}, integ: {len(integs)})")

        # Enqueue sub-playbooks not yet seen — fetch by ID when available
        for sp_id, sp_name in sub_pbs.items():
            if sp_id in playbooks_by_id:
                if pb_name not in playbooks_by_id[sp_id]["parents"]:
                    playbooks_by_id[sp_id]["parents"].append(pb_name)
                continue
            # sp_id may be a real id or a fallback name (when playbookId was missing)
            sub_pb = try_fetch_playbook_by_id(sp_id)
            if sub_pb is None:
                sub_pb = try_fetch_playbook_by_name(sp_name or sp_id)
            if sub_pb is None:
                print(f"  (miss) sub-playbook '{sp_name or sp_id}' not found — will mark as external")
                continue
            queue.append((sub_pb, pb_name))

    # Fetch all automations by scriptId
    print(f"\nFetching {len(automations_seen)} automation(s)...")
    automations_manifest = []
    for script_id in sorted(automations_seen):
        meta = automations_seen[script_id]
        auto = try_fetch_automation_by_id(script_id)
        if auto is None:
            print(f"  (miss) automation id='{script_id}' (name='{meta['name']}') not found")
            automations_manifest.append({
                "id": script_id,
                "name": meta["name"],
                "file": None,
                "used_by_playbooks": sorted(meta["used_by"]),
                "status": "not_found",
            })
            continue
        display_name = auto.get("name") or meta["name"] or script_id
        path = automation_output_path(display_name)
        xsoar_client.save_json(auto, path)
        automations_manifest.append({
            "id": auto.get("id") or script_id,
            "name": display_name,
            "file": path.replace("\\", "/"),
            "used_by_playbooks": sorted(meta["used_by"]),
            "status": "fetched",
        })

    # Fetch all integrations (strip creds). Attribute commands via integrationScript.
    print(f"\nFetching {len(integrations_seen)} integration(s) (credentials stripped)...")
    integrations_manifest = []
    for brand in sorted(integrations_seen):
        meta = integrations_seen[brand]
        integ = try_fetch_integration(brand)
        if integ is None:
            print(f"  (miss) integration '{brand}' not found")
            integrations_manifest.append({
                "brand": brand,
                "file": None,
                "used_by_playbooks": sorted(meta["used_by"]),
                "commands_used": sorted(meta["commands"]),
                "available_commands": [],
                "status": "not_found",
            })
            continue
        cleaned = strip_credentials(integ)
        integration_script = cleaned.get("integrationScript") or {}
        available = sorted({
            c.get("name") for c in integration_script.get("commands", []) if c.get("name")
        })
        path = integration_output_path(cleaned.get("name") or cleaned.get("brand") or brand)
        xsoar_client.save_json(cleaned, path)
        integrations_manifest.append({
            "brand": cleaned.get("brand") or brand,
            "name": cleaned.get("name"),
            "file": path.replace("\\", "/"),
            "used_by_playbooks": sorted(meta["used_by"]),
            "commands_used": sorted(meta["commands"]),
            "available_commands": available,
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
