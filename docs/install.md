# CORE Installation

* Table of Contents
{:toc}

# Overview

This section will describe how to install CORE from source or from a pre-built package.

# Required Hardware

Any computer capable of running Linux should be able to run CORE. Since the physical machine will be hosting numerous 
virtual machines, as a general rule you should select a machine having as much RAM and CPU resources as possible.

# Operating System

CORE requires a Linux operating system because it uses virtualization provided by the kernel. It does not run on 
Windows or Mac OS X operating systems (unless it is running within a virtual machine guest.) The virtualization 
technology that CORE currently uses is Linux network namespaces.

Ubuntu and Fedora/CentOS Linux are the recommended distributions for running CORE. However, these distributions are 
not strictly required. CORE will likely work on other flavors of Linux as well, assuming dependencies are met.

**NOTE: CORE Services determine what run on each node. You may require other software packages depending on the 
services you wish to use. For example, the HTTP service will require the apache2 package.**

# Installed Files

CORE files are installed to the following directories, when the installation prefix is **/usr**.

Install Path | Description
-------------|------------
/usr/bin/core-gui|GUI startup command
/usr/bin/core-daemon|Daemon startup command
/usr/bin/{core-cleanup, coresendmsg, core-manage}|Misc. helper commands/scripts
/usr/lib/core|GUI files
/usr/lib/python{2.7,3}/dist-packages/core|Python modules for daemon/scripts
/etc/core/|Daemon and log configuration files
~/.core/|User-specific GUI preferences and scenario files
/usr/share/core/|Example scripts and scenarios
/usr/share/man/man1/|Command man pages
/etc/init.d/core-daemon|SysV startup script for daemon
/etc/systemd/system/core-daemon.service|Systemd startup script for daemon

# Pre-Req Python Requirements

The newly added gRPC API which depends on python library grpcio is not commonly found within system repos.
To account for this it would be recommended to install the python dependencies using the **requirements.txt** found in
the latest [CORE Release](https://github.com/coreemu/core/releases).

```shell
# for python 2
sudo python -m pip install -r requirements.txt
# for python 3
sudo python3 -m pip install -r requirements.txt
```

## Ubuntu 19.04

Ubuntu 19.04 can provide all the packages needed at the system level and can be installed as follows:
```shell
# python 2
sudo apt install python-configparser python-enum34 python-future python-grpcio python-lxml
# python 3
sudo apt install python3-configparser python3-enum34 python3-future python3-grpcio python3-lxml
```

# Pre-Req Installing OSPF MDR

Virtual networks generally require some form of routing in order to work (e.g. to automatically populate routing 
tables for routing packets from one subnet to another.) CORE builds OSPF routing protocol configurations by 
default when the blue router node type is used. 

* [OSPF MANET Designated Routers](http://www.nrl.navy.mil/itd/ncs/products/ospf-manet) (MDR) - the Quagga routing 
suite with a modified version of OSPFv3, optimized for use with mobile wireless networks. The **mdr** node type 
(and the MDR service) requires this variant of Quagga.

## Ubuntu <= 16.04 and Fedora/CentOS

There is a built package which can be used.

```shell
wget https://downloads.pf.itd.nrl.navy.mil/ospf-manet/quagga-0.99.21mr2.2/quagga-mr_0.99.21mr2.2_amd64.deb
sudo dpkg -i quagga-mr_0.99.21mr2.2_amd64.deb
```

## Ubuntu >= 18.04

Requires building from source, from the latest nightly snapshot.

```shell
wget https://downloads.pf.itd.nrl.navy.mil/ospf-manet/nightly_snapshots/quagga-svnsnap.tgz
tar xzf quagga-svnsnap.tgz
cd quagga
./configure --enable-user=root --enable-group=root --with-cflags=-ggdb \
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

# Installing from Packages

The easiest way to install CORE is using the pre-built packages. The package managers on Ubuntu or Fedora/CentOS 
will help in automatically installing most dependencies for you. 

You can obtain the CORE packages from [CORE Releases](https://github.com/coreemu/core/releases).

## Ubuntu

Ubuntu package defaults to using systemd for running as a service.

```shell
# python2
sudo apt install ./core_python_$VERSION_amd64.deb
# python3
sudo apt install ./core_python3_$VERSION_amd64.deb
```

Run the CORE GUI as a normal user:

```shell
core-gui
```

After running the *core-gui* command, a GUI should appear with a canvas for drawing topologies. 
Messages will print out on the console about connecting to the CORE daemon.

## Fedora/CentOS

**NOTE: tkimg is not required for the core-gui, but if you get an error message about it you can install the package
on CentOS <= 6, or build from source otherwise** 

```shell
# python2
yum install ./core_python_$VERSION_x86_64.rpm
# python3
yum install ./core_python3_$VERSION_x86_64.rpm
```

Disabling SELINUX:

```shell
# change the following in /etc/sysconfig/selinux
SELINUX=disabled

# add the following to the kernel line in /etc/grub.conf
selinux=0

# Fedora 15 and newer, disable sandboxd
# reboot in order for this change to take effect
chkconfig sandbox off
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

Start the CORE daemon.

```shell
# systemd
sudo systemctl daemon-reload
sudo systemctl start core-daemon

# sysv
sudo service core-daemon start
```

Run the CORE GUI as a normal user:

```shell
core-gui
```

After running the *core-gui* command, a GUI should appear with a canvas for drawing topologies. Messages will print out on the console about connecting to the CORE daemon.

# Building and Installing from Source

This option is listed here for developers and advanced users who are comfortable patching and building source code. 
Please consider using the binary packages instead for a simplified install experience.

## Pre-Req All

Python module grpcio-tools is currently needed to generate code from the CORE protobuf file during the build.

```shell
# python2
pip2 install grpcio-tools
# python3
pip3 install grpcio-tools 
```

## Pre-Reqs Ubuntu 18.04

```shell
sudo apt install automake pkg-config gcc libev-dev bridge-utils ebtables python-dev python-setuptools tk libtk-img
```

## Pre-Reqs Ubuntu 16.04

```shell
sudo apt-get install automake bridge-utils ebtables python-dev libev-dev python-setuptools libtk-img
```

## Pre-Reqs CentOS 7

```shell
sudo yum -y install automake gcc python-devel libev-devel tk
```

## Build and Install

```shell
./bootstrap.sh
# for python2
PYTHON=python2 ./configure
# for python3
PYTHON=python3 ./configure 
make
sudo make install
```

## Build Documentation

Building documentation requires python-sphinx not noted above.

```shell
# install python2 sphinx
sudo apt install python-sphinx
sudo yum install python-sphinx
# install python3 sphinx
sudo apt install python3-sphinx
sudo yum install python3-sphinx

./bootstrap.sh
# for python2
PYTHON=python2 ./configure
# for python3
PYTHON=python3 ./configure
make doc
```

## Build Packages
Build package commands, DESTDIR is used to make install into and then for packaging by fpm.

**NOTE: clean the DESTDIR if re-using the same directory**

* Install [fpm](http://fpm.readthedocs.io/en/latest/installing.html)

```shell
./bootstrap.sh
# for python2
PYTHON=python2 ./configure
# for python3
PYTHON=python3 ./configure
make
mkdir /tmp/core-build
make fpm DESTDIR=/tmp/core-build
```

This will produce and RPM and Deb package for the currently configured python version.     
