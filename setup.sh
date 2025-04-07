#!/bin/bash

PYTHON="${PYTHON:=python3}"
PYTHON_DEP="${PYTHON_DEP:=python3}"
PIPX_VERSION=1.7.1
GRPC_VERSION=1.69.0
INVOKE_VERSION=2.2.0
POETRY_VERSION=1.2.1
PROTOBUF_VERSION=5.29.3

# install pre-reqs using yum/apt
if [ -z "${NO_SYSTEM}" ]; then
  if command -v apt &> /dev/null
  then
    echo "setup to install CORE using apt"
    sudo apt install -y ${PYTHON_DEP}-pip ${PYTHON_DEP}-venv python3-pip
    ${PYTHON} -m venv venv
    . ./venv/bin/activate
    python -m pip install pipx==${PIPX_VERSION} protobuf==${PROTOBUF_VERSION} grpcio==${GRPC_VERSION} grpcio-tools==${GRPC_VERSION}
    python -m pipx ensurepath
    python -m pipx install invoke==${INVOKE_VERSION}
    python -m pipx install poetry==${POETRY_VERSION}
  elif command -v yum &> /dev/null
  then
    echo "setup to install CORE using yum"
    sudo yum install -y ${PYTHON_DEP}-pip
    ${PYTHON} -m venv venv
    . ./venv/bin/activate
    python -m pip install pipx==${PIPX_VERSION} protobuf==${PROTOBUF_VERSION} grpcio==${GRPC_VERSION} grpcio-tools==${GRPC_VERSION}
    python -m pipx ensurepath
    python -m pipx install invoke==${INVOKE_VERSION}
    python -m pipx install poetry==${POETRY_VERSION}
  else
    echo "apt/yum was not found"
    echo "install python3, pip, venv, pipx, and invoke to run the automated install"
    exit 1
  fi
fi
