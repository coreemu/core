#!/bin/sh
if [ ! -z "${NO_PYTHON}" ]; then
  exit 0
fi

PYTHON="${PYTHON:=python3}"
if [ ! -z "${NO_VENV}" ]; then
  ${PYTHON} -m pip install /opt/core/core-*.whl
  sed -i 's|$DAEMON|/usr/local/bin/core-daemon|g' /usr/lib/systemd/system/core-daemon.service
else
  ${PYTHON} -m venv /opt/core/venv
  . /opt/core/venv/bin/activate
  pip install --upgrade pip
  pip install /opt/core/core-*.whl
  sed -i 's|$DAEMON|/opt/core/venv/bin/core-daemon|g' /usr/lib/systemd/system/core-daemon.service
  ln -s /opt/core/venv/bin/core-* /usr/bin/
fi
systemctl preset core-daemon
