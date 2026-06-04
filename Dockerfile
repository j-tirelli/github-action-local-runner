# Use an official base image
FROM ubuntu:24.04

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install official GitHub runner dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sudo \
    git \
    jq \
    ca-certificates \
    libicu74 \
    && rm -rf /var/lib/apt/lists/*

# Set up a non-root user for security
RUN useradd -m runner && usermod -aG sudo runner && echo "runner ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER runner
WORKDIR /home/runner

# Download the official GitHub Actions runner package dynamically
# and install all runner dependencies (including .NET runtime deps)
# Architecture is detected at build time so this image works on x64 and arm64
RUN RUNNER_VERSION=$(curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r .tag_name | sed 's/^v//') \
    && ARCH=$(dpkg --print-architecture) \
    && case "${ARCH}" in \
         amd64) RUNNER_ARCH="x64" ;; \
         arm64) RUNNER_ARCH="arm64" ;; \
         arm*)  RUNNER_ARCH="arm" ;; \
         *) echo "Unsupported architecture: ${ARCH}" && exit 1 ;; \
       esac \
    && curl -o actions-runner.tar.gz -L "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-${RUNNER_ARCH}-${RUNNER_VERSION}.tar.gz" \
    && tar xzf ./actions-runner.tar.gz \
    && rm actions-runner.tar.gz \
    && sudo ./bin/installdependencies.sh

# Configure the startup entrypoint script
COPY --chown=runner:runner entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
