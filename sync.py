#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Add the team's open PRs and issues to the right usegalaxy-eu project board, and set their status.

Reads boards.yml. Without --apply it only prints what it would do.
Needs GITHUB_TOKEN with read access to the repos and write access to the boards.
"""

import argparse
import datetime as dt
import fnmatch
import json
import os
import sys
import urllib.request

import yaml

API = "https://api.github.com/graphql"

SEARCH = """
query($q: String!, $after: String) {
  search(type: ISSUE, query: $q, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      __typename
      ... on PullRequest { id url isDraft repository { nameWithOwner } projectItems(first: 20, includeArchived: true) { ...items } }
      ... on Issue { id url repository { nameWithOwner } projectItems(first: 20, includeArchived: true) { ...items } }
    }
  }
}
fragment items on ProjectV2ItemConnection {
  nodes { id isArchived project { id } status: fieldValueByName(name: "Status") { ... on ProjectV2ItemFieldSingleSelectValue { name } } }
}"""

PROJECT = """
query($org: String!, $number: Int!) {
  organization(login: $org) { projectV2(number: $number) {
    id title field(name: "Status") { ... on ProjectV2SingleSelectField { id options { id name } } } } }
}"""

ADD = """mutation($p: ID!, $c: ID!) { addProjectV2ItemById(input: {projectId: $p, contentId: $c}) { item { id } } }"""

SET_STATUS = """mutation($p: ID!, $i: ID!, $f: ID!, $o: String!) {
  updateProjectV2ItemFieldValue(input: {projectId: $p, itemId: $i, fieldId: $f, value: {singleSelectOptionId: $o}}) { projectV2Item { id } }
}"""


def gql(query, **variables):
    req = urllib.request.Request(
        API,
        json.dumps({"query": query, "variables": variables}).encode(),
        {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    if body.get("errors"):
        # Search results can point at boards in other orgs we may not read; those fields come back null.
        # Anything else (or no data at all) is a real failure.
        if not body.get("data") or any(e.get("type") not in ("FORBIDDEN", "NOT_FOUND") for e in body["errors"]):
            raise RuntimeError(json.dumps(body["errors"]))
    return body["data"]


def route(repo, cfg):
    """The board a repo belongs to, or None. Skips skip_repos and the team's own personal repos."""
    repo = repo.lower()
    if repo.split("/")[0] in {p.lower() for p in cfg["people"]}:
        return None
    if repo in {r.lower() for r in cfg.get("skip_repos", [])}:
        return None
    for board in cfg["boards"]:
        if any(fnmatch.fnmatchcase(repo, pattern.lower()) for pattern in board["repos"]):
            return board
    return None


def matches(status, wanted):
    """Board option names carry emoji ("👀 In review"), config uses the plain words. "" means no status."""
    if wanted == "":
        return not status
    return bool(status) and wanted.lower() in status.lower()


def wanted_status(node, board):
    """The status a card should move to, or None to leave it alone."""
    rules = board.get("status")
    if board["mode"] != "status" or not rules or node["__typename"] != "PullRequest":
        return None
    return rules["draft_pr"] if node["isDraft"] else rules["open_pr"]


def plan_card(node, board, project_id):
    """What to do for one PR/issue on its board: (add?, target status or None)."""
    item = next((i for i in (node["projectItems"] or {}).get("nodes", []) if i and i["project"]["id"] == project_id), None)
    if item and item["isArchived"]:
        return False, None  # someone archived it on purpose
    current = ((item or {}).get("status") or {}).get("name")
    target = wanted_status(node, board)
    if target is None or matches(current, target):
        return item is None, None
    if not any(matches(current, m) for m in board["status"]["may_move_from"]):
        return item is None, None  # moved by hand to Blocked, Ready, ...
    return item is None, target


def search(query):
    after = None
    while True:
        page = gql(SEARCH, q=query, after=after)["search"]
        yield from (n for n in page["nodes"] if n)
        if not page["pageInfo"]["hasNextPage"]:
            return
        after = page["pageInfo"]["endCursor"]


def load_project(ref):
    org, number = ref.split("/")
    return gql(PROJECT, org=org, number=int(number))["organization"]["projectV2"]


def option_id(project, name):
    found = [o["id"] for o in project["field"]["options"] if matches(o["name"], name)]
    if len(found) != 1:
        sys.exit(f"{project['title']}: status {name!r} matches {len(found)} options, need exactly 1")
    return found[0]


def main():
    ap = argparse.ArgumentParser(description="Sync the team's open PRs and issues to the usegalaxy-eu project boards.")
    ap.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "boards.yml"))
    ap.add_argument("--apply", action="store_true", help="make the changes (default: only print them)")
    args = ap.parse_args()
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    for board in cfg["boards"]:
        if board["mode"] not in ("off", "add", "status"):  # unquoted `off` in YAML reads as false
            sys.exit(f"{board['name']}: mode must be \"off\", \"add\" or \"status\", got {board['mode']!r}")

    since = (dt.date.today() - dt.timedelta(days=cfg["max_age_days"])).isoformat()
    nodes = {}
    for person in cfg["people"]:
        for q in (f"is:pr author:{person}", f"assignee:{person}"):
            for n in search(f"{q} is:open archived:false updated:>={since}"):
                nodes[n["id"]] = n

    projects, lines = {}, []
    for node in sorted(nodes.values(), key=lambda n: n["url"]):
        board = route(node["repository"]["nameWithOwner"], cfg)
        if not board or board["mode"] == "off":
            continue
        if board["project"] not in projects:
            projects[board["project"]] = load_project(board["project"])
        project = projects[board["project"]]
        add, target = plan_card(node, board, project["id"])
        if not add and not target:
            continue
        option = option_id(project, target) if target else None  # checked in dry runs too
        lines.append(f"- {'add' if add else 'move'} {node['url']} on {board['name']}" + (f" -> {target}" if target else ""))
        if not args.apply:
            continue
        if add:
            item_id = gql(ADD, p=project["id"], c=node["id"])["addProjectV2ItemById"]["item"]["id"]
        else:
            item_id = next(i["id"] for i in node["projectItems"]["nodes"] if i and i["project"]["id"] == project["id"])
        if target:
            gql(SET_STATUS, p=project["id"], i=item_id, f=project["field"]["id"], o=option)

    head = f"{'Changed' if args.apply else 'Dry run, would change'}: {len(lines)} cards ({len(nodes)} open items checked, updated since {since})"
    report = "\n".join([head, *lines])
    print(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(report + "\n")


if __name__ == "__main__":
    main()
