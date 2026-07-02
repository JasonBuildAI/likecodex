# Minimal sandbox image for LikeCodex agent commands.
FROM python:3.11-slim

# Install common tools that coding tasks may need.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    nodejs \
    npm \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Rust for sandbox compilation tasks
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y 2>/dev/null || true
ENV PATH="/root/.cargo/bin:${PATH}"

# Create a non-root user for safer execution.
RUN useradd -m -u 1000 likecodex && mkdir -p /workspace && chown likecodex:likecodex /workspace
USER likecodex
WORKDIR /workspace

# Resource limits applied by docker run --memory=2g --cpus=2
# Default: 2GB memory, 2 CPU cores, no network access

# Default command keeps the container alive briefly so exec can attach.
CMD ["sleep", "3600"]
