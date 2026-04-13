FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

# Install any global system utilities
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install or upgrade any global Python packages
RUN pip install --upgrade pip && \
    pip install --no-cache-dir PyYAML
