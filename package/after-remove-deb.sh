#!/bin/sh
if [ ! -z "${NO_PYTHON}" ]; then
  exit 0
fi

PYTHON="${PYTHON:=python3}"
if [ ! -z "${NO_VENV}" ]; then
  ${PYTHON} -m pip uninstall -y core
else
  ${PYTHON} -m venv /opt/core/venv
  . /opt/core/venv/bin/activate
  pip uninstall -y core
  rm -rf /opt/core/venv
  rm -rf /opt/core/share
fi
