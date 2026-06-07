# GitHub Action Local Runner

A Docker image that runs a self-hosted GitHub Actions runner using the official [actions/runner](https://github.com/actions/runner) package on Ubuntu 24.04.

## What it does

- Pulls the latest official GitHub Actions runner release at build time
- Runs as a non-root `runner` user for security
- Configures and registers itself against a GitHub repository at container startup using environment variables
- Keeps the runner process alive for the lifetime of the container

## Usage

The image is published to GitHub Container Registry and rebuilt automatically on every push to `main`:

```
ghcr.io/j-tirelli/github-action-local-runner:latest
```

### Run (recommended — using a GitHub App)

A GitHub App acts as a dedicated service account for your runner infrastructure. Set it up once and every `docker run` is fully automated — no expiring tokens, no manual steps, and access scoped precisely to the repos you choose.

Store your `.pem` private key somewhere stable on the host (e.g. `~/.github-app-keys/my-runner.pem`) and mount it read-only into the container.

```bash
docker run -d --name my-local-runner \
  -e REPO_URL="https://github.com/<owner>/<repo>" \
  -e GITHUB_APP_ID="<your-app-id>" \
  -e GITHUB_APP_INSTALLATION_ID="<your-installation-id>" \
  -e GITHUB_APP_PRIVATE_KEY_PATH="/secrets/key.pem" \
  -v ~/.github-app-keys/my-runner.pem:/secrets/key.pem:ro \
  -e RUNNER_NAME="my-local-runner" \
  -e LABELS="self-hosted,linux,x64" \
  ghcr.io/j-tirelli/github-action-local-runner:latest
```

See [Setting up a GitHub App](#setting-up-a-github-app) below for the one-time setup steps.

### Run (using a Personal Access Token)

A fine-grained PAT is simpler to set up than a GitHub App and does not require manual token regeneration. However, it carries `Administration: Read & Write` on the target repo (enough to delete it), so treat it as a sensitive credential.

```bash
docker run -d --name my-local-runner \
  -e REPO_URL="https://github.com/<owner>/<repo>" \
  -e GITHUB_PAT="<your-personal-access-token>" \
  -e RUNNER_NAME="my-local-runner" \
  -e LABELS="self-hosted,linux,x64" \
  ghcr.io/j-tirelli/github-action-local-runner:latest
```

### Run (legacy — using a registration token)

Registration tokens expire after ~1 hour and must be regenerated manually each time you start the container.

```bash
docker run -d --name my-local-runner \
  -e REPO_URL="https://github.com/<owner>/<repo>" \
  -e RUNNER_TOKEN="<your-registration-token>" \
  -e RUNNER_NAME="my-local-runner" \
  -e LABELS="self-hosted,linux,x64" \
  ghcr.io/j-tirelli/github-action-local-runner:latest
```

---

### Environment variables

| Variable                      | Required | Description                                                                                        |
| ----------------------------- | -------- | -------------------------------------------------------------------------------------------------- |
| `REPO_URL`                    | Yes      | Full URL of the GitHub repository to register the runner against                                   |
| `GITHUB_APP_ID`               | One of   | Numeric ID of your GitHub App                                                                      |
| `GITHUB_APP_INSTALLATION_ID`  | One of   | Installation ID from the App's installation URL                                                    |
| `GITHUB_APP_PRIVATE_KEY_PATH` | With App | Path to the mounted `.pem` private key file                                                        |
| `GITHUB_APP_PRIVATE_KEY`      | With App | Raw PEM content as an env var (alternative to mounting a file)                                     |
| `GITHUB_PAT`                  | One of   | Personal Access Token with `repo` scope (classic) or `Administration: Read & Write` (fine-grained) |
| `RUNNER_TOKEN`                | One of   | Short-lived registration token from **Settings → Actions → Runners**                               |
| `RUNNER_NAME`                 | Yes      | Display name for the runner (shown in GitHub UI)                                                   |
| `LABELS`                      | Yes      | Comma-separated list of labels to assign to the runner                                             |

> At least one of `GITHUB_APP_ID`+`GITHUB_APP_INSTALLATION_ID`, `GITHUB_PAT`, or `RUNNER_TOKEN` must be provided. If `GITHUB_APP_ID` and `GITHUB_APP_INSTALLATION_ID` are both set they take priority.

---

### Setting up a GitHub App

This is a one-time process that takes about 10 minutes.

1. **Create the App** — go to [GitHub → Settings → Developer settings → GitHub Apps → New GitHub App](https://github.com/settings/apps/new)
   - Give it a name (e.g. `my-local-runner`)
   - Set the homepage URL to anything (e.g. `https://github.com/j-tirelli/github-action-local-runner`)
   - Leave the callback URL blank
   - Uncheck **Active** under Webhooks
   - Under **Repository permissions**, set:
     - **Administration** → **Read & Write**
     - **Actions** → **Read**
   - Click **Create GitHub App**

2. **Note your App ID** — shown at the top of the App's settings page

3. **Generate a private key** — click **Generate a private key** on the same page. A `.pem` file downloads. Store it securely (e.g. `~/.github-app-keys/my-runner.pem`) and set permissions to `644`:

   ```bash
   chmod 644 ~/.github-app-keys/my-runner.pem
   ```

4. **Install the App** — click **Install App** in the left sidebar, choose your account, and select the repo(s) you want runners for. Click **Install**.

5. **Note your Installation ID** — after installing, GitHub redirects to a URL like `github.com/settings/installations/67890`. The number at the end is your Installation ID.

6. **Run the container** — use the command from the [GitHub App section](#run-recommended--using-a-github-app) above.

#### Multiple repos

Install the App on each additional repo (App settings → Install App → configure). The same `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, and `.pem` work for all of them — just change `REPO_URL` and `RUNNER_NAME` per container.

#### Headless / no file mount

If you can't mount a file (e.g. running via a web UI like Cosmos Cloud), pass the raw PEM content as `GITHUB_APP_PRIVATE_KEY` instead of using `GITHUB_APP_PRIVATE_KEY_PATH`.

---

## Building locally

```bash
docker build --build-arg CACHE_BUST=$(date +%s) -t github-action-local-runner .
```

The `CACHE_BUST` arg forces the runner binary to be re-downloaded, ensuring you always get the latest version.

---

## Notes

- The runner registers with `--replace`, so restarting the container with the same `RUNNER_NAME` re-registers it without conflict.
- Use `--name` on `docker run` so you can reliably target the container with `docker logs` and `docker rm`.
- While idle the runner uses a persistent long-poll connection to GitHub. CPU and network usage are negligible.
- GitHub App private keys can be revoked at any time from the App settings page without affecting any other credentials or repos.
