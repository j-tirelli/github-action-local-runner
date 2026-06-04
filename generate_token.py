#!/usr/bin/env python3
"""
Exchanges GitHub App credentials for a runner registration token.

Required environment variables:
  GITHUB_APP_ID               — The App's numeric ID
  GITHUB_APP_INSTALLATION_ID  — The installation ID for the target account/org
  REPO_PATH                   — "<owner>/<repo>" derived from REPO_URL
  GITHUB_APP_PRIVATE_KEY_PATH — Path to the .pem file (preferred)
    OR
  GITHUB_APP_PRIVATE_KEY      — Raw PEM content as an env var

Prints the registration token to stdout.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

import jwt  # PyJWT


def api_post(url: str, auth_token: str) -> dict:
    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {auth_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"ERROR: GitHub API request to {url} failed ({exc.code}): {body}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    app_id = os.environ.get("GITHUB_APP_ID")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")
    repo_path = os.environ.get("REPO_PATH")

    if not all([app_id, installation_id, repo_path]):
        print("ERROR: GITHUB_APP_ID, GITHUB_APP_INSTALLATION_ID, and REPO_PATH must all be set.", file=sys.stderr)
        sys.exit(1)

    key_path = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH")
    if key_path:
        try:
            with open(key_path, "r") as f:
                private_key = f.read()
        except OSError as exc:
            print(f"ERROR: Could not read private key file '{key_path}': {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
        if not private_key:
            print("ERROR: Either GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY must be set.", file=sys.stderr)
            sys.exit(1)

    # Build and sign the App JWT (valid for 10 minutes)
    now = int(time.time())
    app_jwt = jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": app_id},
        private_key,
        algorithm="RS256",
    )

    # Exchange App JWT for a short-lived installation access token
    installation_token = api_post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        app_jwt,
    )["token"]

    # Exchange installation token for a runner registration token
    registration_token = api_post(
        f"https://api.github.com/repos/{repo_path}/actions/runners/registration-token",
        installation_token,
    )["token"]

    print(registration_token, end="")


if __name__ == "__main__":
    main()
