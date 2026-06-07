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


def build_app_jwt(app_id: str, private_key: str, now: int = None) -> str:
    """Sign and return a GitHub App JWT. now is injectable for testing."""
    if now is None:
        now = int(time.time())
    return jwt.encode(
        {"iat": now - 60, "exp": now + 600, "iss": app_id},
        private_key,
        algorithm="RS256",
    )


def load_private_key() -> str:
    """Load the private key from GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY."""
    key_path = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH")
    if key_path:
        try:
            with open(key_path, "r") as f:
                return f.read()
        except OSError as exc:
            print(f"ERROR: Could not read private key file '{key_path}': {exc}", file=sys.stderr)
            sys.exit(1)

    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
    if not private_key:
        print("ERROR: Either GITHUB_APP_PRIVATE_KEY_PATH or GITHUB_APP_PRIVATE_KEY must be set.", file=sys.stderr)
        sys.exit(1)
    # Some UIs (e.g. Cosmos Cloud) strip real newlines from env var values.
    # Support both literal \n sequences and actual newlines.
    return private_key.replace("\\n", "\n")


def get_registration_token(app_id: str, installation_id: str, repo_path: str, private_key: str) -> str:
    """Full exchange: private key → App JWT → installation token → registration token."""
    app_jwt = build_app_jwt(app_id, private_key)

    installation_token = api_post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        app_jwt,
    )["token"]

    registration_token = api_post(
        f"https://api.github.com/repos/{repo_path}/actions/runners/registration-token",
        installation_token,
    )["token"]

    return registration_token


def main() -> None:
    app_id = os.environ.get("GITHUB_APP_ID")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")
    repo_path = os.environ.get("REPO_PATH")

    if not all([app_id, installation_id, repo_path]):
        print("ERROR: GITHUB_APP_ID, GITHUB_APP_INSTALLATION_ID, and REPO_PATH must all be set.", file=sys.stderr)
        sys.exit(1)

    private_key = load_private_key()
    token = get_registration_token(app_id, installation_id, repo_path, private_key)
    print(token, end="")


if __name__ == "__main__":
    main()
