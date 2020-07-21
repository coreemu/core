# Installation

* Table of Contents
{:toc}

## Overview

CORE provides a script to help automate installing all required software
to build and run, including a python virtual environment to run it all in.

The following tools will be leveraged during installation:

|Tool|Description|
|---|---|
|[pip](https://pip.pypa.io/en/stable/)|used to install pipx|
|[pipx](https://pipxproject.github.io/pipx/)|used to install standalone python tools (invoke, poetry)|
|[invoke](http://www.pyinvoke.org/)|used to run provided tasks (install, daemon, gui, tests, etc)|
|[poetry](https://python-poetry.org/)|used to install the managed python virtual environment for running CORE|

## Required Hardware

Any computer capable of running Linux should be able to run CORE. Since the physical machine will be hosting numerous
containers, as a general rule you should select a machine having as much RAM and CPU resources as possible.

## Supported Linux Distributions

Plan is to support recent Ubuntu and CentOS LTS releases.

Verified:
* Ubuntu - 18.04, 20.04
* CentOS - 7.8, 8.0*

> **NOTE:** Ubuntu 20.04 requires installing legacy ebtables for WLAN
> functionality

> **NOTE:** CentOS 8 does not provide legacy ebtables support, WLAN will not
> function properly

> **NOTE:** CentOS 8 does not have the netem kernel mod available by default

CentOS 8 Enabled netem:
```shell
sudo yum update
# restart into updated kernel
sudo yum install -y kernel-modules-extra
sudo modprobe sch_netem
```

## Utility Requirements

* iproute2 4.5+ is a requirement for bridge related commands
* ebtables not backed by nftables

## Upgrading

Please make sure to uninstall the previous installation of CORE cleanly
before proceeding to install.

Previous install was built from source:
```shell
cd <CORE_REPO>
sudo make uninstall
make clean
./bootstrap.sh clean
```

Installed from previously built packages:
```shell
# centos
sudo yum remove core
# ubuntu
sudo apt remove core
```

## Automated Installation

The automated install will install the various tools needed to help automate
the CORE installation (python3, pip, pipx, invoke, poetry). The script will
also automatically clone, build, and install the latest version of OSPF MDR.
Finally it will install CORE scripts and a systemd service, which have
been modified to use the installed poetry created virtual environment.

After installation has completed you should be able to run the various
CORE scripts for running core.

> **NOTE:** provide a prefix that will be found on path when running as sudo
> if the default prefix is not valid

```shell
# clone CORE repo
git clone https://github.com/coreemu/core.git
cd core

# run install script
# script usage: install.sh [-d] [-v]
#
# -v enable verbose install
# -d enable developer install
# -p install prefix, defaults to /usr/local
./install.sh
```

### Unsupported Linux Distribution

If you are on an unsupported distribution, you can look into the
[install.sh](https://github.com/coreemu/core/blob/master/install.sh)
and
[tasks.py](https://github.com/coreemu/core/blob/master/tasks.py)
files to see the various commands ran to install CORE and translate them to
your use case, assuming it is possible.

If you get install down entirely, feel free to contribute and help others.

## Installed Scripts

After the installation complete it will have installed the following scripts.

| Name | Description |
|---|---|
| core-daemon | runs the backed core server providing TLV and gRPC APIs |
| core-gui | runs the legacy tcl/tk based GUI |
| core-pygui | runs the new python/tk based GUI |
| core-cleanup | tool to help removed lingering core created containers, bridges, directories |
| core-imn-to-xml | tool to help automate converting a .imn file to .xml format |
| core-route-monitor | tool to help monitor traffic across nodes and feed that to SDT |
| core-service-update | tool to update automate modifying a legacy service to match current naming |
| coresendmsg | tool to send TLV API commands from command line |
| core-cli | tool to query, open xml files, and send commands using gRPC |
| core-manage | tool to add, remove, or check for services, models, and node types |

## Running User Scripts

If you create your own python scripts to run CORE directly or using the gRPC/TLV
APIs you will need to make sure you are running them within context of the
installed virtual environment.

> **NOTE:** the following assumes CORE has been installed successfully

There is an invoke task to help with this case.
```shell
cd <CORE_REPO>
inv -h run
Usage: inv[oke] [--core-opts] run [--options] [other tasks here ...]

Docstring:
  runs a user script in the core virtual environment

Options:
  -f STRING, --file=STRING   script file to run in the core virtual environment
  -s, --sudo                 run script as sudo
```

Another way would be to enable the core virtual environment shell. Which
would allow you to run scripts in a more **normal** way.
```shell
cd <CORE_REPO>/daemon
poetry shell
python run /path/to/script.py
```

## Manually Install EMANE

EMANE can be installed from deb or RPM packages or from source. See the
[EMANE GitHub](https://github.com/adjacentlink/emane) for full details.

There is an invoke task to help with installing EMANE, but has issues,
which attempts to build EMANE from source, but has issue on systems with
 older protobuf-compilers.

```shell
cd <CORE_REPO>
inv install-emane
```

Alternatively, you can
[build EMANE](https://github.com/adjacentlink/emane/wiki/Build)
from source and install the python
bindings into the core virtual environment.

The following would install the EMANE python bindings after being
successfully built.
```shell
cd <CORE_REPO>/daemon
poetry run pip install <EMANE_REPO>/src/python
```

## Using Invoke Tasks

The invoke tool installed by way of pipx provides conveniences for running
CORE tasks to help ensure usage of the create python virtual environment.

```shell
inv --list

Available tasks:

  daemon            start core-daemon
  install           install core, poetry, scripts, service, and ospf mdr
  install-emane     install emane and the python bindings
  install-scripts   install core script files, modified to leverage virtual environment
  install-service   install systemd core service
  run               runs a user script in the core virtual environment
  test              run core tests
  test-emane        run core emane tests
  test-mock         run core tests using mock to avoid running as sudo
  uninstall         uninstall core, scripts, service, virtual environment, and clean build directory
```

Print help for a given task:
```shell
inv -h install

Usage: inv[oke] [--core-opts] install [--options] [other tasks here ...]

Docstring:
  install core, poetry, scripts, service, and ospf mdr

Options:
  -d, --dev                    install development mode
  -p STRING, --prefix=STRING   prefix where scripts are installed, default is /usr/local
  -v, --verbose                enable verbose
```
