#!/bin/bash

# exit on error
set -e

# parse arguments
dev=""
verbose=""
prefix=""
local=""
while getopts "dvlp:" opt; do
  case ${opt} in
  d)
    dev="-d"
    ;;
  v)
    verbose="-v"
    ;;
  l)
    local="-l"
    ;;
  p)
    prefix="-p ${OPTARG}"
    ;;
  \?)
    echo "script usage: $(basename $0) [-v] [-d] [-l] [-p <prefix>]" >&2
    echo "" >&2
    echo "-v enable verbose install" >&2
    echo "-d enable developer install" >&2
    echo "-l enable local install, not compatible with developer install" >&2
    echo "-p install prefix, defaults to /usr/local" >&2
    exit 1
    ;;
  esac
done
shift $((OPTIND - 1))

# install pre-reqs using yum/apt
if command -v apt &> /dev/null
then
  echo "setup to install CORE using apt"
  sudo apt install -y python3-pip python3-venv
elif command -v yum &> /dev/null
then
  echo "setup to install CORE using yum"
  sudo yum install -y python3-pip
else
  echo "apt/yum was not found"
  echo "install python3 and invoke to run the automated install"
  echo "inv -h install"
  exit 1
fi

# install pip/invoke to run install with provided options
python3 -m pip install --user pipx==0.16.4
python3 -m pipx ensurepath
export PATH=$PATH:~/.local/bin
pipx install invoke
inv install ${dev} ${verbose} ${local} ${prefix}
