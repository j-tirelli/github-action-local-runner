#!/bin/bash
# Configure the runner using environment variables
./config.sh --url "${REPO_URL}" --token "${RUNNER_TOKEN}" --name "${RUNNER_NAME}" --labels "${LABELS}" --unattended --replace

# Start the runner and keep the container alive
./run.sh
