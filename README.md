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

### Run (recommended — using a PAT)

Create a GitHub [Personal Access Token](https://github.com/settings/tokens) with the **`repo`** scope (classic token) or the **`Administration: Read & Write`** permission (fine-grained token). Set it once and reuse it every time you start the container — no manual token generation needed.

```bash
docker run -d \
  -e REPO_URL="https://github.com/<owner>/<repo>" \
  -e GITHUB_PAT="<your-personal-access-token>" \
  -e RUNNER_NAME="my-local-runner" \
  -e LABELS="self-hosted,linux,x64" \
  github-action-local-runner
```

### Run (legacy — using a registration token)

If you prefer to supply a short-lived registration token directly you can still do so. Tokens expire after ~1 hour so you must regenerate one each time you start the container.

```bash
docker run -d \
  -e REPO_URL="https://github.com/<owner>/<repo>" \
  -e RUNNER_TOKEN="<your-registration-token>" \
  -e RUNNER_NAME="my-local-runner" \
  -e LABELS="self-hosted,linux,x64" \
  github-action-local-runner
```

### Environment variables

| Variable       | Required | Description                                                                                                   |
| -------------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| `REPO_URL`     | Yes      | Full URL of the GitHub repository to register the runner against                                              |
| `GITHUB_PAT`   | One of   | Personal Access Token with `repo` scope. The container fetches a registration token automatically at startup. |
| `RUNNER_TOKEN` | One of   | Short-lived registration token from **Settings → Actions → Runners**. Use this if you cannot supply a PAT.    |
| `RUNNER_NAME`  | Yes      | Display name for the runner (shown in GitHub UI)                                                              |
| `LABELS`       | Yes      | Comma-separated list of labels to assign to the runner                                                        |

### Creating a Personal Access Token

1. Go to **GitHub → Settings → Developer settings → Personal access tokens**
2. Choose **Tokens (classic)** and click **Generate new token**
3. Select the **`repo`** scope
4. Copy the token and pass it as `GITHUB_PAT`

## Notes

- The runner registers with `--replace`, so restarting the container with the same `RUNNER_NAME` will re-register it without conflict.
- When using `GITHUB_PAT`, a fresh registration token is fetched automatically on every container start — no manual steps required.
