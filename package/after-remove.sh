#!/bin/sh
if [ -v NO_PYTHON ]; then
  exit 0
fi

PYTHON="${PYTHON:=python3}"
if [ -v NO_VENV ]; then
  ${PYTHON} -m pip uninstall -y core
else
  ${PYTHON} -m venv /opt/core/venv
  . /opt/core/venv/bin/activate
  pip uninstall -y core
fi
