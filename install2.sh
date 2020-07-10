#!/bin/bash

# exit on error
set -e

# detect os/ver for install type
os=""
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  os=${ID}
fi

# parse arguments
dev=""
verbose=""
while getopts "dv" opt; do
  case ${opt} in
  d)
    dev="-d"
    ;;
  v)
    verbose="-v"
    ;;
  \?)
    echo "script usage: $(basename $0) [-d] [-v]" >&2
    echo "" >&2
    echo "-v enable verbose install" >&2
    echo "-d enable developer install" >&2
    exit 1
    ;;
  esac
done
shift $((OPTIND - 1))

echo "installing CORE for ${os}"
case ${os} in
"ubuntu")
  sudo apt install -y python3-pip python3-venv
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
export PATH=$PATH:~/.local/bin
pipx install invoke
inv install ${dev} ${verbose}
