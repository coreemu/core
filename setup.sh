#!/bin/bash

# check if uv/uvx is installed
if ! command -v "uv" >/dev/null 2>&1; then
    echo "uv is not installed and available: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# install python 3.13 with uv
uv python install 3.13

# install uv tool invoke
uv tool install invoke==2.2.0

# sync daemon dependencies used for building protos
cd daemon && uv sync --locked
