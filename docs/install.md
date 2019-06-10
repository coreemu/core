
# CORE Installation

* Table of Contents
{:toc}

# Overview

This section will describe how to set up a CORE machine. Note that the easiest way to install CORE is using a binary package on Ubuntu or Fedora/CentOS (deb or rpm) using the distribution's package manager to automatically install dependencies.

Ubuntu and Fedora/CentOS Linux are the recommended distributions for running CORE. However, these distributions are not strictly required. CORE will likely work on other flavors of Linux as well.

The primary dependencies are Tcl/Tk (8.5 or newer) for the GUI, and Python 2.7 for the CORE daemon.

CORE files are installed to the following directories, when the installation prefix is */usr*.

Install Path | Description
-------------|------------
/usr/bin/core-gui|GUI startup command
/usr/bin/core-daemon|Daemon startup command
/usr/bin/|Misc. helper commands/scripts
/usr/lib/core|GUI files
/usr/lib/python2.7/dist-packages/core|Python modules for daemon/scripts
/etc/core/|Daemon configuration files
~/.core/|User-specific GUI preferences and scenario files
/usr/share/core/|Example scripts and scenarios
/usr/share/man/man1/|Command man pages
/etc/init.d/core-daemon|SysV startup script for daemon
/etc/systemd/system/core-daemon.service|Systemd startup script for daemon

## Prerequisites

A Linux operating system is required. The GUI uses the Tcl/Tk scripting toolkit, and the CORE daemon requires Python. Details of the individual software packages required can be found in the installation steps.

## Required Hardware

Any computer capable of running Linux should be able to run CORE. Since the physical machine will be hosting numerous virtual machines, as a general rule you should select a machine having as much RAM and CPU resources as possible.

## Required Software

CORE requires a Linux operating system because it uses virtualization provided by the kernel. It does not run on Windows or Mac OS X operating systems (unless it is running within a virtual machine guest.) The virtualization technology that CORE currently uses is Linux network namespaces.

The CORE GUI requires the X.Org X Window system (X11), or can run over a remote X11 session. For specific Tcl/Tk, Python, and other libraries required to run CORE.

**NOTE: CORE *Services* determine what run on each node. You may require other software packages depending on the services you wish to use. For example, the *HTTP* service will require the *apache2* package.**

## Installing from Packages

The easiest way to install CORE is using the pre-built packages. The package managers on Ubuntu or Fedora/CentOS will automatically install dependencies for you. You can obtain the CORE packages from [CORE GitHub](https://github.com/coreemu/core/releases).

### Installing from Packages on Ubuntu

Install Quagga for routing. If you plan on working with wireless networks, we recommend installing [OSPF MDR](http://www.nrl.navy.mil/itd/ncs/products/ospf-manet) (replace *amd64* below with *i386* if needed to match your architecture):

```shell
wget https://downloads.pf.itd.nrl.navy.mil/ospf-manet/quagga-0.99.21mr2.2/quagga-mr_0.99.21mr2.2_amd64.deb
sudo dpkg -i quagga-mr_0.99.21mr2.2_amd64.deb
```

Or, for the regular Ubuntu version of Quagga:

```shell
sudo apt-get install quagga
```

Install the CORE deb packages for Ubuntu from command line.

```shell
sudo dpkg -i python-core_*.deb
sudo dpkg -i core-gui_*.deb
```

Start the CORE daemon as root, the systemd installation will auto start the daemon, but you can use the commands below if need be.

```shell
# systemd
sudo systemctl start core-daemon

# sysv
sudo service core-daemon start
```

Run the CORE GUI as a normal user:

```shell
core-gui
```

After running the *core-gui* command, a GUI should appear with a canvas for drawing topologies. Messages will print out on the console about connecting to the CORE daemon.

### Installing from Packages on Fedora/CentOS

The commands shown here should be run as root. The *x86_64* architecture is shown in the examples below, replace with *i686* is using a 32-bit architecture.

**CentOS 7 Only: in order to install *tkimg* package you must build from source.**

Make sure the system is up to date.

```shell
yum update
```

**Optional (Fedora 17+): Fedora 17 and newer have an additional prerequisite providing the required netem kernel modules (otherwise skip this step and have the package manager install it for you.)**

```shell
yum install kernel-modules-extra
```

Install Quagga for routing. If you plan on working with wireless networks, we recommend installing [OSPF MDR](http://www.nrl.navy.mil/itd/ncs/products/ospf-manet):

```shell
wget https://downloads.pf.itd.nrl.navy.mil/ospf-manet/quagga-0.99.21mr2.2/quagga-0.99.21mr2.2-1.el6.x86_64.rpm
sudo yum install quagga-0.99.21mr2.2-1.el6.x86_64.rpm
```

Or, for the regular Fedora/CentOS version of Quagga:

```shell
yum install quagga
```

Install the CORE RPM packages and automatically resolve dependencies:

```shell
yum install python-core_*.rpm
yum install core-gui_*.rpm
```

Turn off SELINUX by setting *SELINUX=disabled* in the */etc/sysconfig/selinux* file, and adding *selinux=0* to the kernel line in your */etc/grub.conf* file; on Fedora 15 and newer, disable sandboxd using ```chkconfig sandbox off```; you need to reboot in order for this change to take effect

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

Start the CORE daemon as root.

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

### Installing from Source

This option is listed here for developers and advanced users who are comfortable patching and building source code. Please consider using the binary packages instead for a simplified install experience.

To build CORE from source on Ubuntu, first install these development packages. These packages are not required for normal binary package installs.

You can obtain the CORE source from the [CORE GitHub](https://github.com/coreemu/core) page. Choose either a stable release version or the development snapshot available in the *nightly_snapshots* directory.

#### Install Requirements

##### Ubuntu 18.04 Requirements

```shell
sudo apt install automake pkg-config gcc libev-dev bridge-utils ebtables python-dev python-sphinx python-setuptools python-lxml python-enum34 tk libtk-img
```

##### Ubuntu 16.04 Requirements

```shell
sudo apt-get install automake bridge-utils ebtables python-dev libev-dev python-sphinx python-setuptools python-enum34 python-lxml libtk-img
```


##### CentOS 7 with Gnome Desktop Requirements

```shell
sudo yum -y install automake gcc python-devel libev-devel python-sphinx tk python-lxml python-enum34
```

#### Download and Extract Source Code

##### Download
You can obtain the CORE source code from the [CORE GitHub](https://github.com/coreemu/core) page.

##### Extract
```shell
tar xzf core-*.tar.gz
cd core-*
```

#### Tradional Autotools Build
```shell
./bootstrap.sh
./configure
make
sudo make install
```

#### Build Documentation
```shell
./bootstrap.sh
./configure
make doc
```

#### Build Packages
Install fpm: http://fpm.readthedocs.io/en/latest/installing.html
Build package commands, DESTDIR is used for gui packaging only

```shell
./bootstrap.sh
./configure
make
mkdir /tmp/core-gui
make fpm DESTDIR=/tmp/core-gui

```
This will produce:
     
* CORE GUI rpm/deb files
  * core-gui_$VERSION_$ARCH
* CORE ns3 rpm/deb files
  * python-core-ns3_$VERSION_$ARCH
* CORE python rpm/deb files for SysV and systemd service types
  * python-core-sysv_$VERSION_$ARCH
  * python-core-systemd_$VERSION_$ARCH
					    

### Quagga Routing Software

Virtual networks generally require some form of routing in order to work (e.g. to automatically populate routing tables for routing packets from one subnet to another.) CORE builds OSPF routing protocol configurations by default when the blue router node type is used. The OSPF protocol is available from the [Quagga open source routing suit](http://www.quagga.net).

Quagga is not specified as a dependency for the CORE packages because there are two different Quagga packages that you may use:

* [Quagga](http://www.quagga.net) - the standard version of Quagga, suitable for static wired networks, and usually available via your distribution's package manager.

* [OSPF MANET Designated Routers](http://www.nrl.navy.mil/itd/ncs/products/ospf-manet) (MDR) - the Quagga routing suite with a modified version of OSPFv3, optimized for use with mobile wireless networks. The *mdr* node type (and the MDR service) requires this variant of Quagga.

If you plan on working with wireless networks, we recommend installing OSPF MDR; otherwise install the standard version of Quagga using your package manager or from source.

#### Installing Quagga from Packages

To install the standard version of Quagga from packages, use your package manager (Linux).

Ubuntu users:

```shell
sudo apt-get install quagga
```

Fedora/CentOS users:

```shell
sudo yum install quagga
```

To install the Quagga variant having OSPFv3 MDR, first download the appropriate package, and install using the package manager.

Ubuntu users:
```shell
wget https://downloads.pf.itd.nrl.navy.mil/ospf-manet/quagga-0.99.21mr2.2/quagga-mr_0.99.21mr2.2_amd64.deb
sudo dpkg -i quagga-mr_0.99.21mr2.2_amd64.deb
```

Replace *amd64* with *i686* if using a 32-bit architecture.

Fedora/CentOS users:

```shell
wget https://downloads.pf.itd.nrl.navy.mil/ospf-manet/quagga-0.99.21mr2.2/quagga-0.99.21mr2.2-1.el6.x86_64.rpm
sudo yum install quagga-0.99.21mr2.2-1.el6.x86_64.rpm
````

Replace *x86_64* with *i686* if using a 32-bit architecture.

#### Compiling Quagga for CORE

To compile Quagga to work with CORE on Linux:

```shell
wget https://downloads.pf.itd.nrl.navy.mil/ospf-manet/quagga-0.99.21mr2.2/quagga-0.99.21mr2.2.tar.gz
tar xzf quagga-0.99.21mr2.2.tar.gz
cd quagga-0.99
./configure --enable-user=root --enable-group=root --with-cflags=-ggdb \\
    --sysconfdir=/usr/local/etc/quagga --enable-vtysh \\
    --localstatedir=/var/run/quagga
make
sudo make install
```

Note that the configuration directory */usr/local/etc/quagga* shown for Quagga above could be */etc/quagga*, if you create a symbolic link from */etc/quagga/Quagga.conf -> /usr/local/etc/quagga/Quagga.conf* on the host. The *quaggaboot.sh* script in a Linux network namespace will try and do this for you if needed.

If you try to run quagga after installing from source and get an error such as:

```shell
error while loading shared libraries libzebra.so.0
```

this is usually a sign that you have to run ```sudo ldconfig```` to refresh the cache file.

### VCORE

CORE is capable of running inside of a virtual machine, using software such as VirtualBox, VMware Server or QEMU. However, CORE itself is performing machine virtualization in order to realize multiple emulated nodes, and running CORE virtually adds additional contention for the physical resources. **For performance reasons, this is not recommended.** Timing inside of a VM often has problems. If you do run CORE from within a VM, it is recommended that you view the GUI with remote X11 over SSH, so the virtual machine does not need to emulate the video card with the X11 application.

A CORE virtual machine is provided for download, named VCORE. This is the perhaps the easiest way to get CORE up and running as the machine is already set up for you. This may be adequate for initially evaluating the tool but keep in mind the performance limitations of running within VirtualBox or VMware. To install the virtual machine, you first need to obtain VirtualBox from http://www.virtualbox.org, or VMware Server or Player from http://www.vmware.com (this commercial software is distributed for free.) Once virtualization software has been installed, you can import the virtual machine appliance using the *vbox* file for VirtualBox or the *vmx* file for VMware. See the documentation that comes with VCORE for login information.

