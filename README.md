# GitHub Action Local Runner

A Docker image that runs a self-hosted GitHub Actions runner using the official [actions/runner](https://github.com/actions/runner) package on Ubuntu 24.04.

## What it does

- Pulls the latest official GitHub Actions runner release at build time
- Runs as a non-root `runner` user for security
- Configures and registers itself against a GitHub repository at container startup using environment variables
- Keeps the runner process alive for the lifetime of the container

## Usage

### Build

```bash
docker build -t github-action-local-runner .
```

### Run

```bash
docker run -d \
  -e REPO_URL="https://github.com/<owner>/<repo>" \
  -e RUNNER_TOKEN="<your-registration-token>" \
  -e RUNNER_NAME="my-local-runner" \
  -e LABELS="self-hosted,linux,x64" \
  github-action-local-runner
```

### Environment variables

| Variable | Description |
|---|---|
| `REPO_URL` | Full URL of the GitHub repository to register the runner against |
| `RUNNER_TOKEN` | Registration token obtained from the repository's **Settings → Actions → Runners** page |
| `RUNNER_NAME` | Display name for the runner (shown in GitHub UI) |
| `LABELS` | Comma-separated list of labels to assign to the runner |

### Getting a registration token

1. Go to your repository on GitHub
2. Navigate to **Settings → Actions → Runners**
3. Click **New self-hosted runner**
4. Copy the token shown in the configuration step

## Notes

- The runner registers with `--replace`, so restarting the container with the same `RUNNER_NAME` will re-register it without conflict.
- Registration tokens are short-lived (~1 hour). Generate a new one each time you start the container.
