#!/bin/bash
set -e

# Wait for Docker-in-Docker TLS certs to be available (if using DinD)
if [ -n "${DOCKER_HOST}" ] && [ -n "${DOCKER_CERT_PATH}" ]; then
    echo "Waiting for DinD TLS certs at ${DOCKER_CERT_PATH}..."
    until [ -f "${DOCKER_CERT_PATH}/ca.pem" ] && [ -f "${DOCKER_CERT_PATH}/cert.pem" ] && [ -f "${DOCKER_CERT_PATH}/key.pem" ]; do
        sleep 1
    done
    echo "DinD TLS certs found."
fi

# Resolve the registration token.
# Option 1 (preferred): supply GITHUB_PAT — a token is fetched automatically from the API.
# Option 2 (legacy):    supply RUNNER_TOKEN directly (must be regenerated every ~1 hour).
if [ -z "${RUNNER_TOKEN}" ]; then
    if [ -z "${GITHUB_PAT}" ]; then
        echo "ERROR: Either GITHUB_PAT or RUNNER_TOKEN must be set."
        exit 1
    fi
    # Extract "<owner>/<repo>" from the repo URL
    REPO_PATH=$(echo "${REPO_URL}" | sed 's|https://github.com/||')
    echo "Fetching runner registration token for ${REPO_PATH}..."
    RUNNER_TOKEN=$(curl -fsSL \
        -X POST \
        -H "Accept: application/vnd.github+json" \
        -H "Authorization: Bearer ${GITHUB_PAT}" \
        -H "X-GitHub-Api-Version: 2022-11-28" \
        "https://api.github.com/repos/${REPO_PATH}/actions/runners/registration-token" \
        | jq -r .token)
    if [ -z "${RUNNER_TOKEN}" ] || [ "${RUNNER_TOKEN}" = "null" ]; then
        echo "ERROR: Failed to fetch registration token. Check that GITHUB_PAT has the 'repo' scope and REPO_URL is correct."
        exit 1
    fi
    echo "Registration token obtained successfully."
fi

# Configure the runner using environment variables
if ! ./config.sh --url "${REPO_URL}" --token "${RUNNER_TOKEN}" --name "${RUNNER_NAME}" --labels "${LABELS}" --unattended --replace; then
    echo "ERROR: Runner configuration failed."
    exit 1
fi

# Start the runner
./run.sh
