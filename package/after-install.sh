#!/bin/sh
if [ ! -z "${NO_PYTHON}" ]; then
  exit 0
fi

PYTHON="${PYTHON:=python3}"
if [ ! -z "${NO_VENV}" ]; then
  ${PYTHON} -m pip install /opt/core/core-*.whl
  echo "DAEMON=/usr/local/bin/core-daemon" > /opt/core/service
else
  ${PYTHON} -m venv /opt/core/venv
  . /opt/core/venv/bin/activate
  pip install --upgrade pip
  pip install /opt/core/core-*.whl
  echo "DAEMON=/opt/core/venv/bin/core-daemon" > /opt/core/service
fi
