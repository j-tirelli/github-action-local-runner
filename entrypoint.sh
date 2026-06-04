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

# Configure the runner using environment variables
if ! ./config.sh --url "${REPO_URL}" --token "${RUNNER_TOKEN}" --name "${RUNNER_NAME}" --labels "${LABELS}" --unattended --replace; then
    echo "ERROR: Runner configuration failed. The RUNNER_TOKEN may be expired (tokens are valid for 1 hour)."
    echo "Generate a new token at: ${REPO_URL}/settings/actions/runners/new"
    exit 1
fi

# Start the runner
./run.sh
