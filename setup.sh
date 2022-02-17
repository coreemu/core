#!/bin/bash

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
  echo "install python3, pip, venv, pipx, and invoke to run the automated install"
  exit 1
fi

# install tooling for invoke based installation
python3 -m pip install --user pipx==0.16.4
python3 -m pipx ensurepath
export PATH=$PATH:~/.local/bin
pipx install invoke==1.4.1
pipx install poetry==1.1.12
