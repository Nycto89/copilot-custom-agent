"""
Fetch a playbook from Cortex XSOAR 6.14 by name or ID.

Usage:
    python scripts/python/fetch-playbook.py --name "EDL Update"
    python scripts/python/fetch-playbook.py --id <playbook-id>

Output:
    Saves the playbook JSON to investigation/playbooks/<sanitized-name>.json
    Prints the output path and any referenced sub-playbooks.
"""

import argparse
import sys
import os

# Add scripts/python to path so xsoar_client can be imported when run from repo root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xsoar_client


def fetch_by_name(name):
    """Search for a playbook by name and return the first exact match."""
    body = {
        "query": f'name:"{name}"',
        "page": 0,
        "size": 5,
    }
    result = xsoar_client.request("POST", "/playbook/search", body=body)
    playbooks = result.get("playbooks", [])

    if not playbooks:
        print(f"ERROR: No playbook found with name: {name}", file=sys.stderr)
        sys.exit(1)

    # Prefer exact name match
    for pb in playbooks:
        if pb.get("name", "").lower() == name.lower():
            return pb

    # Fall back to first result if no exact match
    print(f"No exact match for '{name}'. Using closest result: '{playbooks[0].get('name')}'")
    return playbooks[0]


def fetch_by_id(playbook_id):
    """Fetch a playbook by its ID."""
    result = xsoar_client.request("GET", f"/playbook/{playbook_id}")
    if not result:
        print(f"ERROR: No playbook found with ID: {playbook_id}", file=sys.stderr)
        sys.exit(1)
    return result


def extract_sub_playbooks(playbook):
    """Extract names of sub-playbooks referenced in task definitions."""
    sub_playbooks = []
    tasks = playbook.get("tasks", {})
    for task_id, task_data in tasks.items():
        task_info = task_data.get("task", {})
        # Sub-playbook tasks have type "playbook" or reference a playbookName
        if task_data.get("type") == "playbook" or task_info.get("playbookName"):
            pb_name = task_info.get("playbookName") or task_info.get("name", "")
            if pb_name and pb_name not in sub_playbooks:
                sub_playbooks.append(pb_name)
    return sub_playbooks


def main():
    parser = argparse.ArgumentParser(description="Fetch an XSOAR playbook by name or ID.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", help="Playbook name to search for")
    group.add_argument("--id", dest="playbook_id", help="Playbook ID to fetch directly")
    args = parser.parse_args()

    if args.name:
        playbook = fetch_by_name(args.name)
    else:
        playbook = fetch_by_id(args.playbook_id)

    # Determine output path
    pb_name = playbook.get("name", "unnamed-playbook")
    filename = xsoar_client.sanitize_filename(pb_name) + ".json"
    output_path = os.path.join("investigation", "playbooks", filename)

    # Save
    xsoar_client.save_json(playbook, output_path)

    # Report sub-playbooks
    sub_playbooks = extract_sub_playbooks(playbook)
    if sub_playbooks:
        print(f"\nReferenced sub-playbooks ({len(sub_playbooks)}):")
        for sp in sub_playbooks:
            print(f"  - {sp}")
        print("\nTo fetch a sub-playbook, run:")
        print(f'  python scripts/python/fetch-playbook.py --name "<sub-playbook-name>"')

    # Summary
    task_count = len(playbook.get("tasks", {}))
    input_count = len(playbook.get("inputs", []))
    print(f"\nPlaybook: {pb_name}")
    print(f"Tasks: {task_count}")
    print(f"Inputs: {input_count}")


if __name__ == "__main__":
    main()
