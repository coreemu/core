# Installation
* Table of Contents
{:toc}

## Overview
CORE provides a script to help automate the installation of dependencies,
build and install, and either generate a CORE specific python virtual environment
or build and install a python wheel.

> **WARNING:** if Docker is installed, the default iptable rules will block CORE traffic

### Requirements
Any computer capable of running Linux should be able to run CORE. Since the physical machine will be hosting numerous
containers, as a general rule you should select a machine having as much RAM and CPU resources as possible.

* Linux Kernel v3.3+
* iproute2 4.5+ is a requirement for bridge related commands
* nftables compatible kernel and nft command line tool

### Supported Linux Distributions
Plan is to support recent Ubuntu and CentOS LTS releases.

Verified:
* Ubuntu - 18.04, 20.04
* CentOS - 7.8, 8.0

> **NOTE:** CentOS 8 does not have the netem kernel mod available by default

CentOS 8 Enabled netem:
```shell
sudo yum update
# restart into updated kernel
sudo yum install -y kernel-modules-extra
sudo modprobe sch_netem
```

### Tools Used
The following tools will be leveraged during installation:

| Tool                                        | Description                                                           |
|---------------------------------------------|-----------------------------------------------------------------------|
| [pip](https://pip.pypa.io/en/stable/)       | used to install pipx                                                  |
| [pipx](https://pipxproject.github.io/pipx/) | used to install standalone python tools (invoke, poetry)              |
| [invoke](http://www.pyinvoke.org/)          | used to run provided tasks (install, uninstall, reinstall, etc)       |
| [poetry](https://python-poetry.org/)        | used to install python virtual environment or building a python wheel |

### Files
The following is a list of files that would be installed after running the automated installation.

> **NOTE:** the default install prefix is /usr/local, but can be changed as noted below

* executable files
  * `<prefix>/bin/{core-daemon, core-gui, vcmd, vnoded, etc}`
* tcl/tk gui files
  * `<prefix>/lib/core`
  * `<prefix>/share/core/icons`
* example imn files
  * `<prefix>/share/core/examples`
* python files
  * poetry virtual env
    * `cd <repo>/daemon && poetry env info`
    * `~/.cache/pypoetry/virtualenvs/`
  * local python install
    * default install path for python3 installation of a wheel
    * `python3 -c "import core; print(core.__file__)"`
* configuration files
  * `/etc/core/{core.conf, logging.conf}`
* ospf mdr repository files
  * `<repo>/../ospf-mdr`
* emane repository files
  * `<repo>/../emane`

### Installed Executables
After the installation complete it will have installed the following scripts.

| Name                | Description                                                                  |
|---------------------|------------------------------------------------------------------------------|
| core-cleanup        | tool to help removed lingering core created containers, bridges, directories |
| core-cli            | tool to query, open xml files, and send commands using gRPC                  |
| core-daemon         | runs the backed core server providing TLV and gRPC APIs                      |
| core-gui            | runs the legacy tcl/tk based GUI                                             |
| core-imn-to-xml     | tool to help automate converting a .imn file to .xml format                  |
| core-manage         | tool to add, remove, or check for services, models, and node types           |
| core-pygui          | runs the new python/tk based GUI                                             |
| core-python         | provides a convenience for running the core python virtual environment       |
| core-route-monitor  | tool to help monitor traffic across nodes and feed that to SDT               |
| core-service-update | tool to update automate modifying a legacy service to match current naming   |
| coresendmsg         | tool to send TLV API commands from command line                              |

## Upgrading from Older Release
Please make sure to uninstall any previous installations of CORE cleanly
before proceeding to install.

Clearing out a current install from 7.0.0+, making sure to provide options
used for install (`-l` or `-p`).
```shell
cd <CORE_REPO>
inv uninstall <options>
```

Previous install was built from source for CORE release older than 7.0.0:
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
First we will need to clone and navigate to the CORE repo.
```shell
# clone CORE repo
git clone https://github.com/coreemu/core.git
cd core
# install dependencies to run installation task
./setup.sh
# run the following or open a new terminal
source ~/.bashrc
# Ubuntu
inv install
# CentOS
inv install -p /usr
```

First you can use `setup.sh` as a convenience to install tooling for running invoke tasks:

> **NOTE:** `setup.sh` will attempt to determine your OS by way of `/etc/os-release`, currently it supports
> attempts to install OSs that are debian/redhat like (yum/apt).

* python3, pip, venv
* pipx 0.16.4 via pip
* invoke 1.4.1 via pipx
* poetry 1.1.12 via pipx

Then you can run `inv install <options>`:
* installs system dependencies for building core
* installs core into poetry managed virtual environment or locally, if flag is passed
* installs scripts pointing to appropriate python location based on install type
* installs systemd service pointing to appropriate python location based on install type
* clone/build/install working version of [OPSF MDR](https://github.com/USNavalResearchLaboratory/ospf-mdr)

> **NOTE:** installing locally comes with its own risks, it can result it potential
> dependency conflicts with system package manager installed python dependencies

> **NOTE:** provide a prefix that will be found on path when running as sudo,
> if the default prefix /usr/local will not be valid

```shell
inv -h install

Usage: inv[oke] [--core-opts] install [--options] [other tasks here ...]

Docstring:
  install core, poetry, scripts, service, and ospf mdr

Options:
  -d, --dev                          install development mode
  -i STRING, --install-type=STRING   used to force an install type, can be one of the following (redhat, debian)
  -l, --local                        determines if core will install to local system, default is False
  -o, --[no-]ospf                    disable ospf installation
  -p STRING, --prefix=STRING         prefix where scripts are installed, default is /usr/local
  -v, --verbose                      enable verbose

# install core to virtual environment
./install.sh -p <prefix>

# install core locally
./install.sh -p <prefix> -l
```

After installation has completed you should be able to run `core-daemon` and `core-gui`.

## Using Invoke Tasks
The invoke tool installed by way of pipx provides conveniences for running
CORE tasks to help ensure usage of the create python virtual environment.

```shell
inv --list

Available tasks:

  install         install core, poetry, scripts, service, and ospf mdr
  install-emane   install emane python bindings into the core virtual environment
  reinstall       run the uninstall task, get latest from specified branch, and run install task
  test            run core tests
  test-emane      run core emane tests
  test-mock       run core tests using mock to avoid running as sudo
  uninstall       uninstall core, scripts, service, virtual environment, and clean build directory
```

### Enabling Service
After installation, the core service is not enabled by default. If you desire to use the
service, run the following commands.

```shell
sudo systemctl enable core-daemon
sudo systemctl start core-daemon
```

### Unsupported Linux Distribution
For unsupported OSs you could attempt to do the following to translate
an installation to your use case.

* make sure you have python3.6+ with venv support
* make sure you have python3 invoke available to leverage `<repo>/tasks.py`

```shell
# this will print the commands that would be ran for a given installation
# type without actually running them, they may help in being used as
# the basis for translating to your OS
inv install --dry -v -p <prefix> -i <install type>
```

## Dockerfile Install
You can leverage the provided Dockerfile, to run and launch CORE within a Docker container.

```shell
# clone core
git clone https://github.com/coreemu/core.git
cd core
# build image
sudo docker build -t core .
# start container
sudo docker run -itd --name core -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw --privileged core
# enable xhost access to the root user
xhost +local:root
# launch core-gui
sudo docker exec -it core core-gui
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

The recommended way to install EMANE is using prebuilt packages, otherwise
you can follow their instructions for installing from source. Installation
information can be found [here](https://github.com/adjacentlink/emane/wiki/Install).

There is an invoke task to help install the EMANE bindings into the CORE virtual
environment, when needed.
```shell
cd <CORE_REPO>
inv install-emane
```
