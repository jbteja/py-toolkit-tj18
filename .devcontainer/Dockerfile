FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

# Install or Update system utilities
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip
