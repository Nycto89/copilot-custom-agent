"""
Fetch a playbook and its entire dependency tree from Cortex XSOAR 6.14.

Recursively walks sub-playbooks, then fetches every automation and integration
referenced anywhere in the tree, plus one-shot reference catalogs (incident
fields, indicator types) the doc generator uses for cross-linking. Cycle-safe.
Writes a manifest.json that the xsoar-workflow-documentation skill consumes to
generate linked documentation.

Usage:
    python scripts/python/fetch-workflow.py --name "EDL Update"
    python scripts/python/fetch-workflow.py --id <playbook-id>

Output:
    investigation/playbooks/<name>.json        (one per playbook in tree)
    investigation/automations/<name>.json      (one per referenced automation)
    investigation/integrations/<name>.json     (one per referenced integration, creds stripped)
    investigation/reference/<catalog>.json     (incident fields, indicator types — fetched once)
    investigation/docs/<root>/manifest.json    (inventory + cross-references + per-task profiles)
"""

import argparse
import json
import re
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

INCIDENT_FIELD_RE = re.compile(r"\$\{\s*incident\.([A-Za-z0-9_]+)")
INDICATOR_FIELD_RE = re.compile(r"\$\{\s*indicator\.([A-Za-z0-9_]+)")


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


def _walk_strings(obj):
    """Yield every string value nested anywhere inside obj."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def _scan_field_refs(obj, pattern):
    found = set()
    for s in _walk_strings(obj):
        for match in pattern.finditer(s):
            found.add(match.group(1))
    return found


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
    """
    Resolve a playbook when we have what the parent task called a 'playbookId'.

    XSOAR 6.x authored content stores either a GUID or the display name in
    task.task.playbookId, so GET /playbook/{id} 400s ('createPlaybookErr')
    whenever the value is actually a name. Search by id first — it tolerates
    both forms and returns an empty list on a miss — then fall back to the
    direct GET for ids that the search indexer hasn't picked up yet.
    """
    body = {"query": f'id:"{playbook_id}"', "page": 0, "size": 5}
    result = xsoar_client.request("POST", "/playbook/search", body=body, allow_errors=True)
    if result:
        playbooks = result.get("playbooks", [])
        for pb in playbooks:
            if pb.get("id") == playbook_id:
                return pb
        if playbooks:
            return playbooks[0]
    result = xsoar_client.request("GET", f"/playbook/{playbook_id}", allow_errors=True)
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


def extract_playbook_profile(playbook):
    """
    Walk a playbook once and emit both dependency refs and a deep per-task profile.

    Returns a dict with:
        sub_playbooks:  {playbook_id: display_name}   — for crawl BFS
        automations:    {script_id: display_name}     — for fetch queue
        integrations:   {brand: set(commands)}        — for fetch queue
        tasks_by_id:    {task_id: task_profile_dict}  — full per-task detail
        type_counts:    {task_type: count}
        incident_fields_referenced:  sorted list of ${incident.X} names
        indicator_fields_referenced: sorted list of ${indicator.X} names
        inputs/outputs: from the playbook record's inputs[]/outputs[] arrays
        starttaskid:    entry point task id
        invocation_samples: list of (script_id|None, brand|None, command|None,
                                      task_id, task_name, arguments) — for
                                      threading into automation/integration
                                      invocation-site manifests.
    """
    sub_playbooks = {}
    automations = {}
    integrations = {}
    tasks_by_id = {}
    type_counts = {}
    incident_fields = set()
    indicator_fields = set()
    invocation_samples = []

    tasks = playbook.get("tasks") or {}
    for task_id, task_data in tasks.items():
        task_info = task_data.get("task") or {}
        task_type = task_data.get("type", "")
        type_counts[task_type] = type_counts.get(task_type, 0) + 1

        script_args = (
            task_data.get("scriptarguments")
            or task_data.get("scriptArguments")
            or {}
        )
        task_name = task_info.get("name")

        if task_type == "playbook":
            pb_id = task_info.get("playbookId")
            pb_name = task_info.get("playbookName") or task_info.get("name")
            key = pb_id or pb_name
            if key:
                sub_playbooks.setdefault(key, pb_name or pb_id)
        elif task_type == "regular":
            script_id = task_info.get("scriptId") or task_info.get("script") or ""
            script_name = task_info.get("scriptName") or script_id

            if "|||" in script_id:
                brand, _, command = script_id.partition("|||")
                if brand and brand not in ("Builtin", ""):
                    integrations.setdefault(brand, set()).add(command)
                    invocation_samples.append({
                        "kind": "integration_command",
                        "brand": brand,
                        "command": command,
                        "task_id": task_id,
                        "task_name": task_name,
                        "arguments": script_args,
                    })
            elif script_id and script_id not in ("Builtin", ""):
                automations.setdefault(script_id, script_name)
                invocation_samples.append({
                    "kind": "automation",
                    "script_id": script_id,
                    "task_id": task_id,
                    "task_name": task_name,
                    "arguments": script_args,
                })

        brand = task_info.get("brand")
        if brand and brand not in ("Builtin", ""):
            integrations.setdefault(brand, set())

        tasks_by_id[task_id] = {
            "id": task_id,
            "name": task_name,
            "type": task_type,
            "description": task_info.get("description"),
            "scriptId": task_info.get("scriptId"),
            "scriptName": task_info.get("scriptName"),
            "scriptArguments": script_args,
            "conditions": task_data.get("conditions"),
            "fieldMapping": task_data.get("fieldMapping"),
            "loop": task_data.get("loop"),
            "form": task_info.get("form"),
            "nexttasks": task_data.get("nexttasks"),
            "continueonerror": task_data.get("continueonerror", False),
            "reputationcalc": task_data.get("reputationcalc"),
            "separatecontext": task_data.get("separatecontext"),
            "playbookId": task_info.get("playbookId"),
            "playbookName": task_info.get("playbookName"),
            "brand": task_info.get("brand"),
        }

        incident_fields |= _scan_field_refs(task_data, INCIDENT_FIELD_RE)
        indicator_fields |= _scan_field_refs(task_data, INDICATOR_FIELD_RE)

    return {
        "sub_playbooks": sub_playbooks,
        "automations": automations,
        "integrations": integrations,
        "tasks_by_id": tasks_by_id,
        "type_counts": type_counts,
        "incident_fields_referenced": sorted(incident_fields),
        "indicator_fields_referenced": sorted(indicator_fields),
        "inputs": playbook.get("inputs") or [],
        "outputs": playbook.get("outputs") or [],
        "starttaskid": playbook.get("starttaskid"),
        "invocation_samples": invocation_samples,
    }


def playbook_output_path(name):
    return os.path.join("investigation", "playbooks", xsoar_client.sanitize_filename(name) + ".json")


def automation_output_path(name):
    return os.path.join("investigation", "automations", xsoar_client.sanitize_filename(name) + ".json")


def integration_output_path(name):
    return os.path.join("investigation", "integrations", xsoar_client.sanitize_filename(name) + ".json")


def reference_output_path(name):
    return os.path.join("investigation", "reference", xsoar_client.sanitize_filename(name) + ".json")


def fetch_reference_catalogs():
    """
    Pull one-shot reference catalogs the doc generator cross-links against.
    Tolerant of 4xx so a limited-permission API key doesn't abort the whole
    crawl — records 'unauthorized' status instead.
    """
    catalogs = [
        ("incident-fields", "GET", "/incidentfields"),
        ("indicator-types", "GET", "/indicatortype"),
    ]
    result = {}
    print("Fetching reference catalogs (incident fields, indicator types)...")
    for slug, method, endpoint in catalogs:
        # Pull raw text first so we can persist whatever XSOAR returned even if
        # it doesn't parse as JSON. Some 6.14 builds return NDJSON, wrapped
        # payloads, or HTML error pages on these endpoints depending on perms.
        text = xsoar_client.request(method, endpoint, allow_errors=True, return_text=True)
        if text is None:
            print(f"  (skip) '{slug}' — endpoint returned 4xx (likely unauthorized)")
            result[slug] = {"status": "unauthorized", "file": None, "count": 0}
            continue
        # Strip UTF-8 BOM and common XSSI prefixes before trying to parse.
        cleaned = text.lstrip("\ufeff").lstrip()
        for prefix in (")]}',\n", ")]}',", ")]}'\n", ")]}'"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].lstrip()
                break

        if not cleaned:
            print(f"  (skip) '{slug}' — empty response body")
            result[slug] = {"status": "empty", "file": None, "count": 0}
            continue

        path = reference_output_path(slug)
        try:
            data = json.loads(cleaned)
        except ValueError as e:
            # Try NDJSON (one JSON object per line) before giving up.
            lines = [ln for ln in cleaned.splitlines() if ln.strip()]
            try:
                data = [json.loads(ln) for ln in lines]
                print(f"  Parsed '{slug}' as NDJSON ({len(data)} entries)")
            except ValueError:
                raw_path = path[:-5] + ".raw.txt"
                os.makedirs(os.path.dirname(raw_path), exist_ok=True)
                with open(raw_path, "w", encoding="utf-8") as f:
                    f.write(text)
                first_char = repr(text[:1]) if text else "<empty>"
                looks_like_html = cleaned[:1] == "<"
                hint = " (response looks like HTML — likely an auth/proxy page, not JSON)" if looks_like_html else ""
                print(f"  (skip) '{slug}' — could not parse as JSON ({e}). First char: {first_char}, length: {len(text)}.{hint} Raw body saved to {raw_path}")
                result[slug] = {
                    "status": "parse_error",
                    "file": None,
                    "raw_file": raw_path.replace("\\", "/"),
                    "count": 0,
                    "error": str(e),
                    "first_char": first_char,
                    "length": len(text),
                }
                continue

        xsoar_client.save_json(data, path)
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict):
            count = len(data.get("items") or data.get("fields") or data)
        else:
            count = 0
        print(f"  Fetched '{slug}' ({count} entries)")
        result[slug] = {
            "status": "fetched",
            "file": path.replace("\\", "/"),
            "count": count,
        }
    return result


def crawl(root_playbook):
    """BFS walk from the root playbook. Returns the manifest dict."""
    playbooks_by_id = {}         # id → playbook record for manifest
    automations_seen = {}        # scriptId → {"name": str, "used_by": set(), "invocations": [...]}
    integrations_seen = {}       # brand → {"used_by": set(), "commands": set(), "invocations": [...]}
    workflow_incident_fields = set()
    workflow_indicator_fields = set()

    queue = deque([(root_playbook, None)])  # (playbook obj, parent playbook name)

    while queue:
        playbook, parent = queue.popleft()
        pb_id = playbook.get("id", "")
        pb_name = playbook.get("name", "unnamed-playbook")

        if pb_id in playbooks_by_id:
            if parent and parent not in playbooks_by_id[pb_id]["parents"]:
                playbooks_by_id[pb_id]["parents"].append(parent)
            print(f"  (skip) '{pb_name}' already fetched — cycle or shared sub-playbook")
            continue

        path = playbook_output_path(pb_name)
        xsoar_client.save_json(playbook, path)

        profile = extract_playbook_profile(playbook)
        sub_pbs = profile["sub_playbooks"]
        autos = profile["automations"]
        integs = profile["integrations"]

        workflow_incident_fields.update(profile["incident_fields_referenced"])
        workflow_indicator_fields.update(profile["indicator_fields_referenced"])

        playbooks_by_id[pb_id] = {
            "id": pb_id,
            "name": pb_name,
            "file": path.replace("\\", "/"),
            "parents": [parent] if parent else [],
            "starttaskid": profile["starttaskid"],
            "inputs": profile["inputs"],
            "outputs": profile["outputs"],
            "type_counts": profile["type_counts"],
            "incident_fields_referenced": profile["incident_fields_referenced"],
            "indicator_fields_referenced": profile["indicator_fields_referenced"],
            "tasks_by_id": profile["tasks_by_id"],
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

        # Roll up per-task invocation samples into the seen-tables so
        # automation and integration docs can render "called by" with task context.
        for sample in profile["invocation_samples"]:
            if sample["kind"] == "automation":
                entry = automations_seen.setdefault(
                    sample["script_id"],
                    {"name": autos.get(sample["script_id"], sample["script_id"]),
                     "used_by": set(), "invocations": []},
                )
                entry["used_by"].add(pb_name)
                entry["invocations"].append({
                    "playbook": pb_name,
                    "playbook_id": pb_id,
                    "task_id": sample["task_id"],
                    "task_name": sample["task_name"],
                    "arguments": sample["arguments"],
                })
            else:  # integration_command
                entry = integrations_seen.setdefault(
                    sample["brand"],
                    {"used_by": set(), "commands": set(), "invocations": []},
                )
                entry["used_by"].add(pb_name)
                entry["commands"].add(sample["command"])
                entry["invocations"].append({
                    "playbook": pb_name,
                    "playbook_id": pb_id,
                    "task_id": sample["task_id"],
                    "task_name": sample["task_name"],
                    "command": sample["command"],
                    "arguments": sample["arguments"],
                })

        # Brand-only entries (integration tasks with no command invocation) still need registration.
        for brand in integs:
            entry = integrations_seen.setdefault(
                brand, {"used_by": set(), "commands": set(), "invocations": []}
            )
            entry["used_by"].add(pb_name)
            entry["commands"].update(integs[brand])

        # Automations referenced by the profile but not captured via invocation_samples
        # (defensive — keeps the old behavior of seeing every dep even on edge cases).
        for script_id, script_name in autos.items():
            entry = automations_seen.setdefault(
                script_id,
                {"name": script_name, "used_by": set(), "invocations": []},
            )
            entry["used_by"].add(pb_name)

        print(f"  Fetched playbook: {pb_name} "
              f"(tasks: {len(profile['tasks_by_id'])}, sub: {len(sub_pbs)}, "
              f"auto: {len(autos)}, integ: {len(integs)})")

        for sp_id, sp_name in sub_pbs.items():
            if sp_id in playbooks_by_id:
                if pb_name not in playbooks_by_id[sp_id]["parents"]:
                    playbooks_by_id[sp_id]["parents"].append(pb_name)
                continue
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
                "invocations": meta["invocations"],
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
            "invocations": meta["invocations"],
            "status": "fetched",
            # Execution-environment fields the doc skill surfaces without re-opening the JSON.
            "type": auto.get("type"),
            "subtype": auto.get("subtype"),
            "dockerImage": auto.get("dockerImage"),
            "runOnce": auto.get("runOnce"),
            "runAs": auto.get("runAs"),
            "sensitive": auto.get("sensitive"),
            "tags": auto.get("tags") or [],
            "comment": auto.get("comment"),
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
                "command_schemas": {},
                "invocations": meta["invocations"],
                "status": "not_found",
            })
            continue
        cleaned = strip_credentials(integ)
        assert isinstance(cleaned, dict)  # integ is always a dict from the API
        integration_script = cleaned.get("integrationScript") or {}
        all_commands = integration_script.get("commands") or []
        available = sorted({c.get("name") for c in all_commands if c.get("name")})
        # Only store full schemas for commands actually invoked in this workflow —
        # keeps the manifest bounded even for integrations with 100+ commands.
        commands_by_name = {c.get("name"): c for c in all_commands if c.get("name")}
        command_schemas = {}
        for cmd in sorted(meta["commands"]):
            schema = commands_by_name.get(cmd)
            if schema is None:
                command_schemas[cmd] = {
                    "description": None,
                    "arguments": [],
                    "outputs": [],
                    "status": "not_found_in_integration",
                }
            else:
                command_schemas[cmd] = {
                    "description": schema.get("description"),
                    "arguments": schema.get("arguments") or [],
                    "outputs": schema.get("outputs") or [],
                    "deprecated": schema.get("deprecated", False),
                }
        path = integration_output_path(cleaned.get("name") or cleaned.get("brand") or brand)
        xsoar_client.save_json(cleaned, path)
        integrations_manifest.append({
            "brand": cleaned.get("brand") or brand,
            "name": cleaned.get("name"),
            "display": cleaned.get("display"),
            "category": cleaned.get("category"),
            "version": cleaned.get("version"),
            "file": path.replace("\\", "/"),
            "used_by_playbooks": sorted(meta["used_by"]),
            "commands_used": sorted(meta["commands"]),
            "available_commands": available,
            "command_schemas": command_schemas,
            "invocations": meta["invocations"],
            "status": "fetched",
        })

    return {
        "root": root_playbook.get("name"),
        "root_id": root_playbook.get("id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "playbooks": list(playbooks_by_id.values()),
        "automations": automations_manifest,
        "integrations": integrations_manifest,
        "workflow_incident_fields": sorted(workflow_incident_fields),
        "workflow_indicator_fields": sorted(workflow_indicator_fields),
        "stats": {
            "playbooks": len(playbooks_by_id),
            "automations": len(automations_manifest),
            "integrations": len(integrations_manifest),
            "incident_fields_referenced": len(workflow_incident_fields),
            "indicator_fields_referenced": len(workflow_indicator_fields),
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

    reference_catalogs = fetch_reference_catalogs()
    print()

    manifest = crawl(root)
    manifest["reference_catalogs"] = reference_catalogs

    manifest_dir = os.path.join("investigation", "docs", xsoar_client.sanitize_filename(root_name))
    manifest_path = os.path.join(manifest_dir, "manifest.json")
    xsoar_client.save_json(manifest, manifest_path)

    s = manifest["stats"]
    print(f"\n{'=' * 60}")
    print(f"Workflow: {root_name}")
    print(f"  Playbooks:          {s['playbooks']}")
    print(f"  Automations:        {s['automations']}")
    print(f"  Integrations:       {s['integrations']}")
    print(f"  Incident fields:    {s['incident_fields_referenced']}")
    print(f"  Indicator fields:   {s['indicator_fields_referenced']}")
    print(f"  Manifest:           {manifest_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
