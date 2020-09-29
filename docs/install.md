# Installation
* Table of Contents
{:toc}

## Overview
CORE provides a script to help automate the installation of dependencies,
build and install, and either generate a CORE specific python virtual environment
or build and install a python wheel.

> **WARNING:** if Docker is installed, the default iptable rules will block CORE traffic

### Tools Used
The following tools will be leveraged during installation:

|Tool|Description|
|---|---|
|[pip](https://pip.pypa.io/en/stable/)|used to install pipx|
|[pipx](https://pipxproject.github.io/pipx/)|used to install standalone python tools (invoke, poetry)|
|[invoke](http://www.pyinvoke.org/)|used to run provided tasks (install, uninstall, reinstall, etc)|
|[poetry](https://python-poetry.org/)|used to install python virtual environment or building a python wheel|

### Files
The following is a list of files that would be installed after running the automated installation.

> **NOTE:** the default install prefix is /usr/local, but can be changed as noted below

* executable files
  * <prefix>/bin/{core-daemon, core-gui, vcmd, vnoded, etc}
* tcl/tk gui files
  * <prefix>/lib/core
  * <prefix>/share/core/icons
* example imn files
  * <prefix>/share/core/examples
* python files
  * poetry virtual env
    * `cd <repo>/daemon && poetry env info`
    * ~/.cache/pypoetry/virtualenvs/
  * local python install
    * default install path for python3 installation of a wheel
    * `python3 -c "import core; print(core.__file__)"`
* configuration files
  * /etc/core/{core.conf, logging.conf}
* ospf mdr repository files
  * <repo>/../ospf-mdr
* emane repository files
  * <repo>/../emane

### Installed Executables
After the installation complete it will have installed the following scripts.

| Name | Description |
|---|---|
| core-cleanup | tool to help removed lingering core created containers, bridges, directories |
| core-cli | tool to query, open xml files, and send commands using gRPC |
| core-daemon | runs the backed core server providing TLV and gRPC APIs |
| core-gui | runs the legacy tcl/tk based GUI |
| core-imn-to-xml | tool to help automate converting a .imn file to .xml format |
| core-manage | tool to add, remove, or check for services, models, and node types |
| core-pygui | runs the new python/tk based GUI |
| core-python | provides a convenience for running the core python virtual environment |
| core-route-monitor | tool to help monitor traffic across nodes and feed that to SDT |
| core-service-update | tool to update automate modifying a legacy service to match current naming |
| coresendmsg | tool to send TLV API commands from command line |

### Required Hardware
Any computer capable of running Linux should be able to run CORE. Since the physical machine will be hosting numerous
containers, as a general rule you should select a machine having as much RAM and CPU resources as possible.

### Supported Linux Distributions
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

### Utility Requirements
The following are known dependencies that will result in errors when not met.

* iproute2 4.5+ is a requirement for bridge related commands
* ebtables not backed by nftables

## Upgrading from Older Release
Please make sure to uninstall any previous installations of CORE cleanly
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

## Automated Install
The automated install will do the following:
* install base tools needed for installation
  * python3, pip, pipx, invoke, poetry
* installs system dependencies for building core
* clone/build/install working version of [OPSF MDR](https://github.com/USNavalResearchLaboratory/ospf-mdr)
* installs core into poetry managed virtual environment or locally, if flag is passed
* installs scripts pointing pointing to appropriate python location based on install type
* installs systemd service pointing to appropriate python location based on install type

After installation has completed you should be able to run `core-daemon` and `core-gui`.

> **NOTE:** installing locally comes with its own risks, it can result it potential
> dependency conflicts with system package manager installed python dependencies

> **NOTE:** provide a prefix that will be found on path when running as sudo,
> if the default prefix /usr/local will not be valid

`install.sh` will attempt to determine your OS by way of `/etc/os-release`, currently it supports
attempts to install OSs that are debian/redhat like (yum/apt).
```shell
# clone CORE repo
git clone https://github.com/coreemu/core.git
cd core

# script usage: install.sh [-v] [-d] [-l] [-p <prefix>]
#
# -v enable verbose install
# -d enable developer install
# -l enable local install, not compatible with developer install
# -p install prefix, defaults to /usr/local

# install core to virtual environment
./install.sh -p <prefix>

# install core locally
./install.sh -p <prefix> -l
```

### Unsupported Linux Distribution
For unsupported OSs you could attempt to do the following to translate
an installation to your use case.

* make sure you have python3.6+ with venv support
* make sure you have python3 invoke available to leverage `<repo>/tasks.py`

```shell
cd <repo>

# Usage: inv[oke] [--core-opts] install [--options] [other tasks here ...]
#
# Docstring:
#   install core, poetry, scripts, service, and ospf mdr
#
# Options:
#   -d, --dev                          install development mode
#   -i STRING, --install-type=STRING
#   -l, --local                        determines if core will install to local system, default is False
#   -p STRING, --prefix=STRING         prefix where scripts are installed, default is /usr/local
#   -v, --verbose                      enable verbose

# install virtual environment
inv install -p <prefix>

# indstall locally
inv install -p <prefix> -l

# this will print the commands that would be ran for a given installation
# type without actually running them, they may help in being used as
# the basis for translating to your OS
inv install --dry -v -p <prefix> -i <install type>
```

## Running User Scripts
If you create your own python scripts to run CORE directly or using the gRPC/TLV
APIs you will need to make sure you are running them within context of the
installed virtual environment. To help support this CORE provides the `core-python`
executable. This executable will allow you to enter CORE's python virtual
environment interpreter or to run a script within it.

For installations installed to a virtual environment:
```shell
core-python <script>
```

For local installations:
```shell
python3 <script>
```

## Installing EMANE
> **NOTE:** installng emane for the virtual environment is known to work for 1.21+
> **NOTE:** automated install currently targets 1.25

There is an invoke task to help with installing EMANE, which attempts to
build EMANE from source, but has issue on systems with older protobuf-compilers.

```shell
cd <CORE_REPO>

# install to virtual environment
inv install-emane

# install locally to system python3
inv install-emane -l
```

Alternatively EMANE can be installed from deb or RPM packages or from source. See the
[EMANE GitHub](https://github.com/adjacentlink/emane) for full details.
With the caveat that the python bindings need to be installed into CORE's
virtualenv, unless installed locally.

### Installing EMANE Python Bindings for Virtual Environment

If you need to just install the EMANE python bindings to the CORE virtual
environment, since you are installing EMANE itself from pre-built packages.
You can run the following

Leveraging the following wiki:
[build EMANE](https://github.com/adjacentlink/emane/wiki/Build)

The following would install the EMANE python bindings after being
successfully built.
```shell
# clone and build emane python bindings
git clone https://github.com/adjacentlink/emane.git
cd emane
./autogen.sh
PYTHON=python3 ./configure --prefix=/usr
cd src/python
make

# install to core virtual environment
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
