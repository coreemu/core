#!/bin/bash

# exit on error
set -e

# detect os/ver for install type
os=""
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  os=${ID}
fi

echo "installing CORE for ${os}"
case ${os} in
"ubuntu")
  sudo apt install -y python3-pip

  ;;
"centos")
  sudo yum install -y python3-pip
  ;;
*)
  echo "unknown OS ID ${os} cannot install"
  ;;
esac

python3 -m pip install --user pipx
python3 -m pipx ensurepath
python3 -m pipx install invoke
inv install
