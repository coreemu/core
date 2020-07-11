# Installing CORE

## Overview

CORE provides a script to help automate installing all required software
to build and run, including a python virtual environment to run it all in.

The following tools will be leveraged during installation:

|Tool|Description|
|---|---|
|pip|used to install pipx|
|pipx|used to install standalone python tools (invoke, poetry)|
|invoke|used to run provided tasks (install, daemon, gui, tests, etc)|
|poetry|used to install the managed python virtual environment for running CORE|

## Supported Linux Distributions

Plan is to support recent Ubuntu and CentOS LTS releases.

Verified:
* Ubuntu - 18.04, 20.04
* CentOS - 7.8, 8.0*

> **NOTE:** Ubuntu 20.04 requires installing legacy ebtables for WLAN
> functionality

> **NOTE:** CentOS 8 does not provide legacy ebtables support, WLAN will not
> function properly

## Running Installation

```shell
# clone CORE repo
git clone https://github.com/coreemu/core.git
cd core
git checkout enhancement/poetry-invoke

# run install script
./install2.sh
```

## Using Invoke Tasks

The invoke tool installed by way of pipx provides conveniences for running
CORE tasks to help ensure usage of the create python virtual environment.

```shell
Available tasks:

  cleanup      run core-cleanup removing leftover core nodes, bridges, directories
  daemon       start core-daemon
  gui          start core-pygui
  install      install core
  test         run core tests
  test-emane   run core emane tests
  test-mock    run core tests using mock to avoid running as sudo
```

Example running the core-daemon task from the root of the repo:
```shell
inv daemon
```

Some tasks are wrappers around command line tools and requires running
them with a slight variation for compatibility. You can enter the
poetry shell to run the script natively.

```shell
# running core-cli as a task requires all options to be provided
# within a string
inv cli "query session -i 1"

# entering the poetry shell to use core-cli natively
cd $REPO/daemon
poetry shell
core-cli query session -i 1

# exit the shell
exit
```
