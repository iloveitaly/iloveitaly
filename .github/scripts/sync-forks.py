#!/usr/bin/env python3
"""
Sync eligible public forks with their upstream repositories.

Rules:
1. If the fork is new (< 2 months old), sync it anyway.
2. If the fork is older (>= 2 months), only sync it if a new branch
   has been added by the user (or coding agent) in the last 2 months.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DAYS_THRESHOLD = 60
ALLOWED_BOTS = {"cursor[bot]"}


def get_authenticated_user(token: str) -> str:
    """Fetch the GitHub login of the authenticated user."""
    req = urllib.request.Request(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "sync-forks",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())["login"]


def fetch_public_forks() -> list[dict]:
    """Fetch all public forks owned by the user using GitHub CLI."""
    cmd = [
        "gh",
        "repo",
        "list",
        "--fork",
        "--visibility=public",
        "--limit",
        "999",
        "--json",
        "nameWithOwner,createdAt,defaultBranchRef",
    ]
    res = subprocess.check_output(cmd)
    return json.loads(res)


def check_recent_branch_creation(
    repo_name: str, token: str, user_login: str, cutoff: datetime.datetime
) -> tuple[str, str] | None:
    """
    Check if a branch was created in the fork by the user or an authorized bot
    since the cutoff date using GitHub's Repository Activity API.
    """
    url = f"https://api.github.com/repos/{repo_name}/activity?activity_type=branch_creation&per_page=10"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "sync-forks",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            activities = json.loads(resp.read().decode())
            for act in activities:
                ts_str = act.get("timestamp")
                if not ts_str:
                    continue
                ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                actor = (act.get("actor") or {}).get("login", "")

                is_user = actor == user_login or actor in ALLOWED_BOTS
                if ts > cutoff and is_user:
                    ref_name = act.get("ref", "unknown-ref")
                    date_str = ts_str[:10]
                    reason = f"branch '{ref_name}' created by {actor} on {date_str}"
                    return repo_name, reason
    except Exception:
        # Ignore individual repo errors (e.g. rate limit, deleted repo, access issues)
        pass
    return None


def get_forks_to_sync(days: int = DAYS_THRESHOLD) -> list[tuple[str, str]]:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        # Fallback to local gh auth token if running locally
        try:
            token = subprocess.check_output(["gh", "auth", "token"]).decode().strip()
        except Exception:
            print("Error: GH_TOKEN or GITHUB_TOKEN environment variable not set.", file=sys.stderr)
            sys.exit(1)

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    user_login = get_authenticated_user(token)

    forks = fetch_public_forks()
    to_sync: list[tuple[str, str]] = []
    to_check: list[str] = []

    for fork in forks:
        created_at_str = fork.get("createdAt")
        created_at = datetime.datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        name = fork["nameWithOwner"]

        if created_at > cutoff:
            reason = f"new fork (< {days}d old, created {created_at_str[:10]})"
            to_sync.append((name, reason))
        else:
            to_check.append(name)

    # Check older forks concurrently
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(check_recent_branch_creation, name, token, user_login, cutoff)
            for name in to_check
        ]
        for future in futures:
            result = future.result()
            if result:
                to_sync.append(result)

    to_sync.sort(key=lambda x: x[0].lower())
    return to_sync


def main():
    parser = argparse.ArgumentParser(description="Sync eligible public forks with upstream.")
    parser.add_argument(
        "--days",
        type=int,
        default=DAYS_THRESHOLD,
        help=f"Cutoff window in days for fork age and branch activity (default: {DAYS_THRESHOLD}).",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Perform 'gh repo sync' on eligible forks directly.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which forks qualify and why without syncing.",
    )
    args = parser.parse_args()

    to_sync = get_forks_to_sync(days=args.days)

    if args.dry_run:
        print(f"Forks eligible for sync ({len(to_sync)}):")
        for name, reason in to_sync:
            print(f"  {name} ({reason})")
        return

    if args.sync:
        print(f"Starting sync for {len(to_sync)} eligible forks...")
        failed = 0
        for name, reason in to_sync:
            print(f"Syncing {name} ({reason})...")
            res = subprocess.run(["gh", "repo", "sync", name])
            if res.returncode != 0:
                print(f"::warning::Failed to sync {name}", file=sys.stderr)
                failed += 1
        if failed > 0:
            print(f"Completed with {failed} failure(s).", file=sys.stderr)
        else:
            print("All eligible forks synced successfully.")
        return

    # Default: Output repo names to stdout, debug reasons to stderr (for piping)
    for name, reason in to_sync:
        print(f"Eligible: {name} ({reason})", file=sys.stderr)
        print(name)


if __name__ == "__main__":
    main()
