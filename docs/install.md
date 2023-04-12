# Installation
* Table of Contents
{:toc}

> **WARNING:** if Docker is installed, the default iptable rules will block CORE traffic

## Overview
CORE currently supports and provides the following install options, with the package
option being preferred.

* [Package based install (rpm/deb)](#package-based-install)
* [Script based install](#script-based-install)
* [Dockerfile based install](#dockerfile-based-install)

### Requirements
Any computer capable of running Linux should be able to run CORE. Since the physical machine will be hosting numerous
containers, as a general rule you should select a machine having as much RAM and CPU resources as possible.

* Linux Kernel v3.3+
* iproute2 4.5+ is a requirement for bridge related commands
* nftables compatible kernel and nft command line tool

### Supported Linux Distributions
Plan is to support recent Ubuntu and CentOS LTS releases.

Verified:
* Ubuntu - 18.04, 20.04, 22.04
* CentOS - 7.8

### Files
The following is a list of files that would be installed after installation.

* executables
  * `<prefix>/bin/{vcmd, vnode}`
  * can be adjusted using script based install , package will be /usr
* python files
  * virtual environment `/opt/core/venv`
  * local install will be local to the python version used
    * `python3 -c "import core; print(core.__file__)"`
  * scripts {core-daemon, core-cleanup, etc}
    * virtualenv `/opt/core/venv/bin`
    * local `/usr/local/bin`
* configuration files
  * `/etc/core/{core.conf, logging.conf}`
* ospf mdr repository files when using script based install
  * `<repo>/../ospf-mdr`

### Installed Scripts
The following python scripts are provided.

| Name                | Description                                                                  |
|---------------------|------------------------------------------------------------------------------|
| core-cleanup        | tool to help removed lingering core created containers, bridges, directories |
| core-cli            | tool to query, open xml files, and send commands using gRPC                  |
| core-daemon         | runs the backed core server providing a gRPC API                             |
| core-gui            | starts GUI                                                                   |
| core-python         | provides a convenience for running the core python virtual environment       |
| core-route-monitor  | tool to help monitor traffic across nodes and feed that to SDT               |
| core-service-update | tool to update automate modifying a legacy service to match current naming   |

### Upgrading from Older Release
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

## Package Based Install

Starting with 9.0.0 there are pre-built rpm/deb packages. You can retrieve the
rpm/deb package from [releases](https://github.com/coreemu/core/releases) page.

The built packages will require and install system level dependencies, as well as running
a post install script to install the provided CORE python wheel. A similar uninstall script
is ran when uninstalling and would require the same options as given, during the install.

> **NOTE:** PYTHON defaults to python3 for installs below, CORE requires python3.9+, pip,
> tk compatibility for python gui, and venv for virtual environments

Examples for install:
```shell
# recommended to upgrade to the latest version of pip before installation
# in python, can help avoid building from source issues
sudo <python> -m pip install --upgrade pip
# install vcmd/vnoded, system dependencies,
# and core python into a venv located at /opt/core/venv
sudo <yum/apt> install -y ./<package>
# disable the venv and install to python directly
sudo NO_VENV=1 <yum/apt> install -y ./<package>
# change python executable used to install for venv or direct installations
sudo PYTHON=python3.9 <yum/apt> install -y ./<package>
# disable venv and change python executable
sudo NO_VENV=1 PYTHON=python3.9 <yum/apt> install -y ./<package>
# skip installing the python portion entirely, as you plan to carry this out yourself
# core python wheel is located at /opt/core/core-<version>-py3-none-any.whl
sudo NO_PYTHON=1 <yum/apt> install -y ./<package>
# install python wheel into python of your choosing
sudo <python> -m pip install /opt/core/core-<version>-py3-none-any.whl
```

Example for removal, requires using the same options as install:
```shell
# remove a standard install
sudo <yum/apt> remove core
# remove a local install
sudo NO_VENV=1 <yum/apt> remove core
# remove install using alternative python
sudo PYTHON=python3.9 <yum/apt> remove core
# remove install using alternative python and local install
sudo NO_VENV=1 PYTHON=python3.9 <yum/apt> remove core
# remove install and skip python uninstall
sudo NO_PYTHON=1 <yum/apt> remove core
```

### Installing OSPF MDR
You will need to manually install OSPF MDR for routing nodes, since this is not
provided by the package.

```shell
git clone https://github.com/USNavalResearchLaboratory/ospf-mdr.git
cd ospf-mdr
./bootstrap.sh
./configure --disable-doc --enable-user=root --enable-group=root \
  --with-cflags=-ggdb --sysconfdir=/usr/local/etc/quagga --enable-vtysh \
  --localstatedir=/var/run/quagga
make -j$(nproc)
sudo make install
```

When done see [Post Install](#post-install).

## Script Based Install
The script based installation will install system level dependencies, python library and
dependencies, as well as dependencies for building CORE.

The script based install also automatically builds and installs OSPF MDR, used by default
on routing nodes. This can optionally be skipped.

Installaion will carry out the following steps:
* installs system dependencies for building core
* builds vcmd/vnoded and python grpc files
* installs core into poetry managed virtual environment or locally, if flag is passed
* installs systemd service pointing to appropriate python location based on install type
* clone/build/install working version of [OPSF MDR](https://github.com/USNavalResearchLaboratory/ospf-mdr)

> **NOTE:** installing locally comes with its own risks, it can result it potential
> dependency conflicts with system package manager installed python dependencies

> **NOTE:** provide a prefix that will be found on path when running as sudo,
> if the default prefix /usr/local will not be valid

The following tools will be leveraged during installation:

| Tool                                        | Description                                                           |
|---------------------------------------------|-----------------------------------------------------------------------|
| [pip](https://pip.pypa.io/en/stable/)       | used to install pipx                                                  |
| [pipx](https://pipxproject.github.io/pipx/) | used to install standalone python tools (invoke, poetry)              |
| [invoke](http://www.pyinvoke.org/)          | used to run provided tasks (install, uninstall, reinstall, etc)       |
| [poetry](https://python-poetry.org/)        | used to install python virtual environment or building a python wheel |

First we will need to clone and navigate to the CORE repo.
```shell
# clone CORE repo
git clone https://github.com/coreemu/core.git
cd core

# install dependencies to run installation task
./setup.sh
# skip installing system packages, due to using python built from source
NO_SYSTEM=1 ./setup.sh

# run the following or open a new terminal
source ~/.bashrc

# Ubuntu
inv install
# CentOS
inv install -p /usr
# optionally skip python system packages
inv install --no-python
# optionally skip installing ospf mdr
inv install --no-ospf

# install command options
Usage: inv[oke] [--core-opts] install [--options] [other tasks here ...]

Docstring:
  install core, poetry, scripts, service, and ospf mdr

Options:
  -d, --dev                          install development mode
  -i STRING, --install-type=STRING   used to force an install type, can be one of the following (redhat, debian)
  -l, --local                        determines if core will install to local system, default is False
  -n, --no-python                    avoid installing python system dependencies
  -o, --[no-]ospf                    disable ospf installation
  -p STRING, --prefix=STRING         prefix where scripts are installed, default is /usr/local
  -v, --verbose
```

When done see [Post Install](#post-install).

### Unsupported Linux Distribution
For unsupported OSs you could attempt to do the following to translate
an installation to your use case.

* make sure you have python3.9+ with venv support
* make sure you have python3 invoke available to leverage `<repo>/tasks.py`

```shell
# this will print the commands that would be ran for a given installation
# type without actually running them, they may help in being used as
# the basis for translating to your OS
inv install --dry -v -p <prefix> -i <install type>
```

## Dockerfile Based Install
You can leverage one of the provided Dockerfiles, to run and launch CORE within a Docker container.

Since CORE nodes will leverage software available within the system for a given use case,
make sure to update and build the Dockerfile with desired software.

```shell
# clone core
git clone https://github.com/coreemu/core.git
cd core/dockerfiles
# build image
sudo docker build -t core -f Dockerfile.<centos,ubuntu,oracle> .
# start container
sudo docker run -itd --name core -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw --privileged core
# enable xhost access to the root user
xhost +local:root
# launch core-gui
sudo docker exec -it core core-gui
```

When done see [Post Install](#post-install).

## Installing EMANE
> **NOTE:** installing EMANE for the virtual environment is known to work for 1.21+

The recommended way to install EMANE is using prebuilt packages, otherwise
you can follow their instructions for installing from source. Installation
information can be found [here](https://github.com/adjacentlink/emane/wiki/Install).

There is an invoke task to help install the EMANE bindings into the CORE virtual
environment, when needed. An example for running the task is below and the version
provided should match the version of the packages installed.

You will also need to make sure, you are providing the correct python binary where CORE
is being used.

Also, these EMANE bindings need to be built using `protoc` 3.19+. So make sure
that is available and being picked up on PATH properly.

Examples for building and installing EMANE python bindings for use in CORE:
```shell
# if your system does not have protoc 3.19+
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.19.6/protoc-3.19.6-linux-x86_64.zip
mkdir protoc
unzip protoc-3.19.6-linux-x86_64.zip -d protoc
git clone https://github.com/adjacentlink/emane.git
cd emane
git checkout v1.3.3
./autogen.sh
PYTHON=/opt/core/venv/bin/python ./configure --prefix=/usr
cd src/python
PATH=/opt/protoc/bin:$PATH make
/opt/core/venv/bin/python -m pip install .

# when your system has protoc 3.19+
cd <CORE_REPO>
# example version tag v1.3.3
# overriding python used to leverage the default virtualenv install
PYTHON=/opt/core/venv/bin/python inv install-emane -e <version tag>
# local install that uses whatever python3 refers to
inv install-emane -e <version tag>
```

## Post Install
After installation completes you are now ready to run CORE.

### Resolving Docker Issues
If you have Docker installed, by default it will change the iptables
forwarding chain to drop packets, which will cause issues for CORE traffic.

You can temporarily resolve the issue with the following command:
```shell
sudo iptables --policy FORWARD ACCEPT
```
Alternatively, you can configure Docker to avoid doing this, but will likely
break normal Docker networking usage. Using the setting below will require
a restart.

Place the file contents below in **/etc/docker/docker.json**
```json
{
	"iptables": false
}
```

### Resolving Path Issues
One problem running CORE you may run into, using the virtual environment or locally
can be issues related to your path.

To add support for your user to run scripts from the virtual environment:
```shell
# can add to ~/.bashrc
export PATH=$PATH:/opt/core/venv/bin
```

This will not solve the path issue when running as sudo, so you can do either
of the following to compensate.
```shell
# run command passing in the right PATH to pickup from the user running the command
sudo env PATH=$PATH core-daemon

# add an alias to ~/.bashrc or something similar
alias sudop='sudo env PATH=$PATH'
# now you can run commands like so
sudop core-daemon
```

### Running CORE
The following assumes I have resolved PATH issues and setup the `sudop` alias.

```shell
# in one terminal run the server daemon using the alias above
sudop core-daemon
# in another terminal run the gui client
core-gui
```

### Enabling Service
After installation, the core service is not enabled by default. If you desire to use the
service, run the following commands.

```shell
sudo systemctl enable core-daemon
sudo systemctl start core-daemon
```
