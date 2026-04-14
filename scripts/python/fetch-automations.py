"""
Fetch automation (script) definitions from Cortex XSOAR 6.14.

Usage:
    python scripts/python/fetch-automations.py --name "SetIndicatorDBotScore"
    python scripts/python/fetch-automations.py --id <automation-id>
    python scripts/python/fetch-automations.py --playbook-name "EDL Update"

The --playbook-name option parses a previously fetched playbook JSON to find
all referenced automations, then fetches each one.

Output:
    Saves automation JSON to investigation/automations/<name>.json
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xsoar_client


def fetch_by_name(name):
    """Search for an automation by name."""
    body = {
        "query": f'name:"{name}"',
        "page": 0,
        "size": 5,
    }
    result = xsoar_client.request("POST", "/automation/search", body=body)
    scripts = result.get("scripts", [])

    if not scripts:
        print(f"ERROR: No automation found with name: {name}", file=sys.stderr)
        sys.exit(1)

    for s in scripts:
        if s.get("name", "").lower() == name.lower():
            return s

    print(f"No exact match for '{name}'. Using closest result: '{scripts[0].get('name')}'")
    return scripts[0]


def fetch_by_id(automation_id):
    """Fetch an automation by its ID."""
    result = xsoar_client.request("GET", f"/automation/{automation_id}")
    if not result:
        print(f"ERROR: No automation found with ID: {automation_id}", file=sys.stderr)
        sys.exit(1)
    return result


def extract_automations_from_playbook(playbook_name):
    """Parse a fetched playbook JSON to extract referenced automation/script names."""
    filename = xsoar_client.sanitize_filename(playbook_name) + ".json"
    playbook_path = os.path.join("investigation", "playbooks", filename)

    if not os.path.exists(playbook_path):
        print(f"ERROR: Playbook file not found at {playbook_path}", file=sys.stderr)
        print(f"Fetch it first: python scripts/python/fetch-playbook.py --name \"{playbook_name}\"",
              file=sys.stderr)
        sys.exit(1)

    with open(playbook_path, "r", encoding="utf-8") as f:
        playbook = json.load(f)

    automation_names = set()
    tasks = playbook.get("tasks", {})
    for task_id, task_data in tasks.items():
        task_info = task_data.get("task", {})
        script_name = task_info.get("scriptName") or task_info.get("script")
        if script_name:
            # Strip brand prefix if present (e.g., "Builtin|||SetIncident" -> "SetIncident")
            if "|||" in script_name:
                script_name = script_name.split("|||")[-1]
            automation_names.add(script_name)

    return sorted(automation_names)


def save_automation(automation):
    """Save a single automation to the investigation directory."""
    name = automation.get("name", "unnamed-automation")
    filename = xsoar_client.sanitize_filename(name) + ".json"
    output_path = os.path.join("investigation", "automations", filename)
    xsoar_client.save_json(automation, output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Fetch XSOAR automation scripts by name, ID, or playbook reference."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", help="Automation name to search for")
    group.add_argument("--id", dest="automation_id", help="Automation ID to fetch directly")
    group.add_argument("--playbook-name", dest="playbook_name",
                       help="Fetch all automations referenced by this playbook")
    args = parser.parse_args()

    if args.name:
        automation = fetch_by_name(args.name)
        save_automation(automation)

    elif args.automation_id:
        automation = fetch_by_id(args.automation_id)
        save_automation(automation)

    elif args.playbook_name:
        automation_names = extract_automations_from_playbook(args.playbook_name)
        if not automation_names:
            print(f"No automations referenced in playbook '{args.playbook_name}'.")
            return

        print(f"Found {len(automation_names)} automation(s) referenced in '{args.playbook_name}':")
        for name in automation_names:
            print(f"  - {name}")

        print("\nFetching each automation...")
        fetched = 0
        failed = []
        for name in automation_names:
            try:
                automation = fetch_by_name(name)
                save_automation(automation)
                fetched += 1
            except SystemExit:
                failed.append(name)
                print(f"  Skipping '{name}' (not found or access denied)", file=sys.stderr)

        print(f"\nFetched: {fetched}/{len(automation_names)}")
        if failed:
            print(f"Failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
