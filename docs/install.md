# CORE Installation

* Table of Contents
{:toc}

## Overview

This section will describe how to install CORE from source or from a pre-built package.
CORE has been vetted on Ubuntu 18 and CentOS 7.6. Other versions and distributions
can work, assuming you can get the required packages and versions similar to those
noted below for the tested distributions.

> **NOTE:** iproute2 4.5+ is a requirement for bridge related commands

## Required Hardware

Any computer capable of running Linux should be able to run CORE. Since the physical machine will be hosting numerous
containers, as a general rule you should select a machine having as much RAM and CPU resources as possible.

## Operating System

CORE requires a Linux operating system because it uses namespacing provided by the kernel. It does not run on
Windows or Mac OS X operating systems (unless it is running within a virtual machine guest.) The
technology that CORE currently uses is Linux network namespaces.

Ubuntu and CentOS Linux are the recommended distributions for running CORE. However, these distributions are
not strictly required. CORE will likely work on other flavors of Linux as well, assuming dependencies are met.

> **NOTE:** CORE Services determine what run on each node. You may require other software packages depending on the
services you wish to use. For example, the HTTP service will require the apache2 package.

## Installed Files

CORE files are installed to the following directories by default, when the installation prefix is **/usr**.

Install Path | Description
-------------|------------
/usr/bin/core-gui|GUI startup command
/usr/bin/coretk-gui|BETA Python GUI
/usr/bin/core-daemon|Daemon startup command
/usr/bin/{core-cleanup, coresendmsg, core-manage}|Misc. helper commands/scripts
/usr/lib/core|GUI files
/usr/lib/python{3.6+}/dist-packages/core|Python modules for daemon/scripts
/etc/core/|Daemon and log configuration files
~/.core/|User-specific GUI preferences and scenario files
/usr/share/core/|Example scripts and scenarios
/usr/share/man/man1/|Command man pages
/etc/init.d/core-daemon|SysV startup script for daemon
/usr/lib/systemd/system/core-daemon.service|Systemd startup script for daemon

## Automated Install

There is a helper script in the root of the repository that can help automate
the CORE installation. Some steps require commands be ran as sudo and you
will be prompted for a password. This should work on Ubuntu/CentOS and will
install system dependencies, python dependencies, and CORE. This will target
system installations of python 3.6.

```shell
git clone https://github.com/coreemu/core.git
cd core
./install.sh
```

You can target newer system python versions using the **-v** flag. Assuming
these versions are actually available on your system.

```shell
# ubuntu 3.7
./install.sh -v 3.7
# centos 3.7
./install.sh -v 37
```

## Pre-Req Installing Python

Python 3.6 is the minimum required python version. Newer versions can be used if available.
These steps are needed, since the system packages can not provide all the
dependencies needed by CORE.

### Ubuntu

```shell
sudo apt install python3.6
sudo apt install python3-pip
```

### CentOS

```shell
sudo yum install python36
sudo yum install python3-pip
```

### Dependencies

Install the current python dependencies.

```shell
sudo python3 -m pip install -r requirements.txt
```

## Pre-Req Installing OSPF MDR

Virtual networks generally require some form of routing in order to work (e.g. to automatically populate routing
tables for routing packets from one subnet to another.) CORE builds OSPF routing protocol configurations by
default when the blue router node type is used.

* [OSPF MANET Designated Routers](https://github.com/USNavalResearchLaboratory/ospf-mdr) (MDR) - the Quagga routing
suite with a modified version of OSPFv3, optimized for use with mobile wireless networks. The **mdr** node type
(and the MDR service) requires this variant of Quagga.

### Ubuntu

```shell
sudo apt install libtool gawk libreadline-dev
```

### CentOS

```shell
sudo yum install libtool gawk readline-devel
```

### Build and Install

```shell
git clone https://github.com/USNavalResearchLaboratory/ospf-mdr
cd ospf-mdr
./bootstrap.sh
./configure --disable-doc --enable-user=root --enable-group=root --with-cflags=-ggdb \
    --sysconfdir=/usr/local/etc/quagga --enable-vtysh \
    --localstatedir=/var/run/quagga
make
sudo make install
```

Note that the configuration directory */usr/local/etc/quagga* shown for Quagga above could be */etc/quagga*,
if you create a symbolic link from */etc/quagga/Quagga.conf -> /usr/local/etc/quagga/Quagga.conf* on the host.
The *quaggaboot.sh* script in a Linux network namespace will try and do this for you if needed.

If you try to run quagga after installing from source and get an error such as:

```shell
error while loading shared libraries libzebra.so.0
```

this is usually a sign that you have to run ```sudo ldconfig```` to refresh the cache file.

## Installing from Packages

The easiest way to install CORE is using the pre-built packages. The package managers on Ubuntu or CentOS
will help in automatically installing most dependencies, except for the python ones described previously.

You can obtain the CORE packages from [CORE Releases](https://github.com/coreemu/core/releases).

### Ubuntu

Ubuntu package defaults to using systemd for running as a service.

```shell
sudo apt install ./core_$VERSION_amd64.deb
```

### CentOS

**NOTE: tkimg is not required for the core-gui, but if you get an error message about it you can install the package
on CentOS <= 6, or build from source otherwise**

```shell
yum install ./core_$VERSION_x86_64.rpm
```

Disabling SELINUX:

```shell
# change the following in /etc/sysconfig/selinux
SELINUX=disabled

# add the following to the kernel line in /etc/grub.conf
selinux=0
```

Turn off firewalls:

```shell
systemctl disable firewalld
systemctl disable iptables.service
systemctl disable ip6tables.service
chkconfig iptables off
chkconfig ip6tables off
```

You need to reboot after making these changes, or flush the firewall using

```shell
iptables -F
ip6tables -F
```

## Installing from Source

Steps for building from cloned source code. Python 3.6 is the minimum required version
a newer version can be used below if available.

### Distro Requirements

System packages required to build from source.

#### Ubuntu

```shell
sudo apt install git automake pkg-config gcc libev-dev ebtables iproute2 \
    python3.6 python3.6-dev python3-pip python3-tk tk libtk-img ethtool autoconf
```

#### CentOS

```shell
sudo yum install git automake pkgconf-pkg-config gcc gcc-c++ libev-devel iptables-ebtables iproute \
    python36 python36-devel python3-pip python3-tkinter tk ethtool autoconf
```

### Clone Repository

Clone the CORE repository for building from source.

```shell
git clone https://github.com/coreemu/core.git
```

### Install grpcio-tools

Python module grpcio-tools is currently needed to generate gRPC protobuf code.
Specifically leveraging 1.27.2 to avoid compatibility issues with older versions
of pip pulling down binary files.

```shell
python3 -m pip install --only-binary ":all:" --user grpcio-tools
```

### Build and Install

```shell
./bootstrap.sh
./configure
make
sudo make install
```

## Building Documentation

Building documentation requires python-sphinx not noted above.

```shell
sudo apt install python3-sphinx
sudo yum install python3-sphinx

./bootstrap.sh
./configure
make doc
```

## Building Packages
Build package commands, DESTDIR is used to make install into and then for packaging by fpm.

**NOTE: clean the DESTDIR if re-using the same directory**

* Install [fpm](http://fpm.readthedocs.io/en/latest/installing.html)

```shell
./bootstrap.sh
./configure
make
mkdir /tmp/core-build
make fpm DESTDIR=/tmp/core-build
```

This will produce and RPM and Deb package for the currently configured python version.

## Running CORE

Start the CORE daemon.

```shell
# systemd
sudo systemctl daemon-reload
sudo systemctl start core-daemon

# sysv
sudo service core-daemon start
```

Run the GUI

```shell
# default gui
core-gui

# new beta gui
coretk-gui
```
