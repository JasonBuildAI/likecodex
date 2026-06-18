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

# Create a non-root user for safer execution.
RUN useradd -m -u 1000 likecodex && mkdir -p /workspace && chown likecodex:likecodex /workspace
USER likecodex
WORKDIR /workspace

# Default command keeps the container alive briefly so exec can attach.
CMD ["sleep", "3600"]
