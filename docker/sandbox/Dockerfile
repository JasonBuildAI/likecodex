# Phase 8.5: Full-featured sandbox image for LikeCodex agent commands.
FROM python:3.11-slim

LABEL maintainer="LikeCodex" \
      description="Secure sandbox for agent code execution" \
      version="8.5"

# ------------------------------------------------------------------
# System dependencies — tools needed for coding, compilation, and QA
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Version control
    git \
    # Network & download
    curl \
    wget \
    ca-certificates \
    # JavaScript runtime
    nodejs \
    npm \
    # C/C++ build tools (for native extensions)
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    # Utilities
    jq \
    vim-tiny \
    unzip \
    # Security
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# Install Rust toolchain for compilation tasks
# ------------------------------------------------------------------
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    --default-toolchain stable --profile minimal 2>/dev/null
ENV PATH="/root/.cargo/bin:${PATH}"
RUN rustup --version && cargo --version

# ------------------------------------------------------------------
# Install common Python tools
# ------------------------------------------------------------------
RUN pip install --no-cache-dir --upgrade \
    pip \
    pytest \
    ruff \
    black \
    mypy \
    httpx \
    pydantic

# ------------------------------------------------------------------
# Create non-root user with limited privileges
# ------------------------------------------------------------------
RUN useradd -m -u 1000 likecodex \
    && mkdir -p /workspace \
    && chown likecodex:likecodex /workspace \
    && chmod 755 /workspace

# ------------------------------------------------------------------
# Resource limit labels consumed by docker run (applied at runtime)
# ------------------------------------------------------------------
# --memory=2g --cpus=2 --pids-limit=100 --ulimit nofile=1024:2048
# --security-opt=no-new-privileges:true
# --cap-drop=ALL --cap-add=DAC_OVERRIDE --cap-add=CHOWN

USER likecodex
WORKDIR /workspace

# Default command keeps container alive so exec can attach.
CMD ["sleep", "3600"]
