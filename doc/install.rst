.. This file is part of the CORE Manual
   (c)2012-2013 the Boeing Company

.. include:: constants.txt

.. _Installation:

************
Installation
************

This chapter describes how to set up a CORE machine. Note that the easiest 
way to install CORE is using a binary
package on Ubuntu or Fedora (deb or rpm) using the distribution's package
manager
to automatically install dependencies, see :ref:`Installing_from_Packages`.

Ubuntu and Fedora Linux are the recommended distributions for running CORE. Ubuntu |UBUNTUVERSION| and Fedora |FEDORAVERSION| ship with kernels with support for namespaces built-in. They support the latest hardware. However,
these distributions are not strictly required. CORE will likely work on other 
flavors of Linux, see :ref:`Installing_from_Source`.

The primary dependencies are Tcl/Tk (8.5 or newer) for the GUI, and Python 2.6 or 2.7 for the CORE daemon.

.. index:: install locations
.. index:: paths
.. index:: install paths

CORE files are installed to the following directories. When installing from
source, the :file:`/usr/local` prefix is used in place of :file:`/usr` by
default.

============================================= =================================
Install Path                                  Description
============================================= =================================
:file:`/usr/bin/core-gui`                     GUI startup command
:file:`/usr/sbin/core-daemon`                 Daemon startup command
:file:`/usr/sbin/`                            Misc. helper commands/scripts
:file:`/usr/lib/core`                         GUI files
:file:`/usr/lib/python2.7/dist-packages/core` Python modules for daemon/scripts
:file:`/etc/core/`                            Daemon configuration files
:file:`~/.core/`                              User-specific GUI preferences and scenario files
:file:`/usr/share/core/`                      Example scripts and scenarios
:file:`/usr/share/man/man1/`                  Command man pages
:file:`/etc/init.d/core-daemon`               System startup script for daemon
============================================= =================================


Under Fedora, :file:`/site-packages/` is used instead of :file:`/dist-packages/`
for the Python modules, and :file:`/etc/systemd/system/core-daemon.service`
instead of :file:`/etc/init.d/core-daemon` for the system startup script.


.. _Prerequisites:

Prerequisites
=============

.. index:: Prerequisites

The Linux or FreeBSD operating system is required. The GUI uses the Tcl/Tk scripting toolkit, and the CORE daemon require Python. Details of the individual software packages required can be found in the installation steps.

.. _Required_Hardware:

Required Hardware
-----------------

.. index:: Hardware requirements

.. index:: System requirements

Any computer capable of running Linux or FreeBSD should be able to run CORE. Since the physical machine will be hosting numerous virtual machines, as a general rule you should select a machine having as much RAM and CPU resources as possible. 

A *general recommendation* would be:

* 2.0GHz or better x86 processor, the more processor cores the better
* 2 GB or more of RAM
* about 3 MB of free disk space (plus more for dependency packages such as Tcl/Tk)
* X11 for the GUI, or remote X11 over SSH

The computer can be a laptop, desktop, or rack-mount server. A keyboard, mouse, 
and monitor are not required if a network connection is available
for remotely accessing the machine. A 3D accelerated graphics card 
is not required.

.. _Required_Software:

Required Software
-----------------

CORE requires the Linux or FreeBSD operating systems because it uses virtualization provided by the kernel. It does not run on the Windows or Mac OS X operating systems (unless it is running within a virtual machine guest.) There are two
different virtualization technologies that CORE can currently use: 
Linux network namespaces and FreeBSD jails,
see :ref:`How_Does_it_Work?` for virtualization details.

**Linux network namespaces is the recommended platform.** Development is focused here and it supports the latest features. It is the easiest to install because there is no need to patch, install, and run a special Linux kernel.

FreeBSD |BSDVERSION|-RELEASE may offer the best scalability. If your 
applications run under FreeBSD and you are comfortable with that platform, 
this may be a good choice. Device and application support by BSD
may not be as extensive as Linux.

The CORE GUI requires the X.Org X Window system (X11), or can run over a
remote X11 session. For specific Tcl/Tk, Python, and other libraries required
to run CORE, refer to the :ref:`Installation` section.

.. NOTE::
   CORE :ref:`Services` determine what runs on each node. You may require
   other software packages depending on the services you wish to use.
   For example, the `HTTP` service will require the `apache2` package.


.. _Installing_from_Packages:

Installing from Packages
========================

.. index:: installer

.. index:: binary packages

The easiest way to install CORE is using the pre-built packages. The package
managers on Ubuntu or Fedora will
automatically install dependencies for you. 
You can obtain the CORE packages from the `CORE downloads <http://downloads.pf.itd.nrl.navy.mil/core/packages/>`_ page.

.. _Installing_from_Packages_on_Ubuntu:

Installing from Packages on Ubuntu
----------------------------------

First install the Ubuntu |UBUNTUVERSION| operating system.

.. tip::
   With Debian or Ubuntu 14.04 (trusty) and newer, you can simply install
   CORE using the following command::

     sudo apt-get install core-network

   Proceed to the "Install Quagga for routing." line below to install Quagga.
   The other commands shown in this section apply to binary packages
   downloaded from the CORE website instead of using the Debian/Ubuntu
   repositories.


.. NOTE::
   Linux package managers (e.g. `software-center`, `yum`) will take care
   of installing the dependencies for you when you use the CORE packages.
   You do not need to manually use these installation lines. You do need
   to select which Quagga package to use.


* **Optional:** install the prerequisite packages (otherwise skip this 
  step and have the package manager install them for you.)

  .. parsed-literal::

      # make sure the system is up to date; you can also use synaptic or
      #  update-manager instead of apt-get update/dist-upgrade
      sudo apt-get update
      sudo apt-get dist-upgrade
      sudo apt-get install |APTDEPS| |APTDEPS2| 
    
* Install Quagga for routing. If you plan on working with wireless
  networks, we recommend 
  installing
  `OSPF MDR <http://www.nrl.navy.mil/itd/ncs/products/ospf-manet>`__
  (replace `amd64` below with `i386` if needed 
  to match your architecture):

  .. parsed-literal::

      export URL=http://downloads.pf.itd.nrl.navy.mil/ospf-manet
      wget $URL/|QVER|/|QVERDEB|
      sudo dpkg -i |QVERDEB|


  or, for the regular Ubuntu version of Quagga:
  ::

    sudo apt-get install quagga
    
* Install the CORE deb packages for Ubuntu, using a GUI that automatically
  resolves dependencies (note that the absolute path to the deb file
  must be used with ``software-center``):

  .. parsed-literal::

      software-center /home/user/Downloads/core-daemon\_\ |version|-|COREDEB|
      software-center /home/user/Downloads/core-gui\_\ |version|-|COREDEB2|
    
  or install from command-line:
  
  .. parsed-literal::

      sudo dpkg -i core-daemon\_\ |version|-|COREDEB|
      sudo dpkg -i core-gui\_\ |version|-|COREDEB2|
    
* Start the CORE daemon as root.
  ::

    sudo /etc/init.d/core-daemon start
    
* Run the CORE GUI as a normal user:
  ::

    core-gui
    

After running the ``core-gui`` command, a GUI should appear with a canvas
for drawing topologies. Messages will print out on the console about
connecting to the CORE daemon.

.. _Installing_from_Packages_on_Fedora:

Installing from Packages on Fedora/CentOS
-----------------------------------------

The commands shown here should be run as root. First Install the Fedora
|FEDORAVERSION| or CentOS |CENTOSVERSION| operating system.
The `x86_64` architecture is shown in the
examples below, replace with `i686` is using a 32-bit architecture. Also,
`fc15` is shown below for Fedora 15 packages, replace with the appropriate
Fedora release number.

* **CentOS only:** in order to install the `libev` and `tkimg` prerequisite
  packages, you 
  first need to install  the `EPEL <http://fedoraproject.org/wiki/EPEL>`_ repo
  (Extra Packages for Enterprise Linux):

  ::

    wget http://dl.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm
    yum localinstall epel-release-6-8.noarch.rpm


* **CentOS 7.x only:** as of this writing, the `tkimg` prerequisite package
  is missing from EPEL 7.x, but the EPEL 6.x package can be manually installed
  from 
  `here <http://dl.fedoraproject.org/pub/epel/6/x86_64/repoview/tkimg.html>`_

  ::

    wget http://dl.fedoraproject.org/pub/epel/6/x86_64/tkimg-1.4-1.el6.x86_64.rpm
    yum localinstall tkimg-1.4-1.el6.x86_64.rpm


* **Optional:** install the prerequisite packages (otherwise skip this
  step and have the package manager install them for you.)

  .. parsed-literal::

      # make sure the system is up to date; you can also use the
      #  update applet instead of yum update
      yum update
      yum install |YUMDEPS| |YUMDEPS2|


* **Optional (Fedora 17+):** Fedora 17 and newer have an additional 
  prerequisite providing the required netem kernel modules (otherwise
  skip this step and have the package manager install it for you.)

  ::

    yum install kernel-modules-extra


* Install Quagga for routing. If you plan on working with wireless networks,
  we recommend installing
  `OSPF MDR <http://www.nrl.navy.mil/itd/ncs/products/ospf-manet>`_:

  .. parsed-literal::

      export URL=http://downloads.pf.itd.nrl.navy.mil/ospf-manet
      wget $URL/|QVER|/|QVERRPM|
      yum localinstall |QVERRPM|

  or, for the regular Fedora version of Quagga:
  ::

    yum install quagga
    

* Install the CORE RPM packages for Fedora and automatically resolve
  dependencies:

  .. parsed-literal::

      yum localinstall core-daemon-|version|-|CORERPM| --nogpgcheck
      yum localinstall core-gui-|version|-|CORERPM2| --nogpgcheck
    
  or install from the command-line:

  .. parsed-literal::

      rpm -ivh core-daemon-|version|-|CORERPM|
      rpm -ivh core-gui-|version|-|CORERPM2|
    

* Turn off SELINUX by setting ``SELINUX=disabled`` in the :file:`/etc/sysconfig/selinux` file, and adding ``selinux=0`` to the kernel line in
  your :file:`/etc/grub.conf` file; on Fedora 15 and newer, disable sandboxd using ``chkconfig sandbox off``;
  you need to reboot in order for this change to take effect
* Turn off firewalls with ``systemctl disable firewalld``, ``systemctl disable iptables.service``, ``systemctl disable ip6tables.service`` (``chkconfig iptables off``, ``chkconfig ip6tables off``) or configure them with permissive rules for CORE virtual networks; you need to reboot after making this change, or flush the firewall using ``iptables -F``, ``ip6tables -F``.

* Start the CORE daemon as root. Fedora uses the ``systemd`` start-up daemon
  instead of traditional init scripts. CentOS uses the init script.
  ::

    # for Fedora using systemd:
    systemctl daemon-reload
    systemctl start core-daemon.service
    # or for CentOS:
    /etc/init.d/core-daemon start
    
* Run the CORE GUI as a normal user:
  ::

    core-gui
    

After running the ``core-gui`` command, a GUI should appear with a canvas
for drawing topologies. Messages will print out on the console about
connecting to the CORE daemon.

.. _Installing_from_Source:

Installing from Source
======================

This option is listed here for developers and advanced users who are comfortable patching and building source code. Please consider using the binary packages instead for a simplified install experience.

.. _Installing_from_Source_on_Ubuntu:

Installing from Source on Ubuntu
--------------------------------

To build CORE from source on Ubuntu, first install these development packages.
These packages are not required for normal binary package installs.

.. parsed-literal::

  sudo apt-get install |APTDEPS| \\
      |APTDEPS2| \\
      |APTDEPS3|
  

You can obtain the CORE source from the `CORE source <http://downloads.pf.itd.nrl.navy.mil/core/source/>`_ page. Choose either a stable release version or
the development snapshot available in the `nightly_snapshots` directory. 
The ``-j8`` argument to ``make`` will run eight simultaneous jobs, to speed up 
builds on multi-core systems.

.. parsed-literal::

  tar xzf core-|version|.tar.gz
  cd core-|version|
  ./bootstrap.sh
  ./configure
  make -j8
  sudo make install
  

The CORE Manual documentation is built separately from the :file:`doc/` 
sub-directory in the source. It requires Sphinx:

.. parsed-literal::

  sudo apt-get install python-sphinx
  cd core-|version|/doc
  make html
  make latexpdf


.. _Installing_from_Source_on_Fedora:

Installing from Source on Fedora
--------------------------------

To build CORE from source on Fedora, install these development packages.
These packages are not required for normal binary package installs.

.. parsed-literal::

  yum install |YUMDEPS| \\
  |YUMDEPS2| \\
  |YUMDEPS3|
  

.. NOTE::
      For a minimal X11 installation, also try these packages::
      
          yum install xauth xterm urw-fonts

You can obtain the CORE source from the `CORE source <http://downloads.pf.itd.nrl.navy.mil/core/source/>`_ page. Choose either a stable release version or
the development snapshot available in the :file:`nightly_snapshots` directory.
The ``-j8`` argument to ``make`` will run eight simultaneous jobs, to speed up 
builds on multi-core systems. Notice the ``configure`` flag to tell the build
system that a systemd service file should be installed under Fedora.

.. parsed-literal::

  tar xzf core-|version|.tar.gz
  cd core-|version|
  ./bootstrap.sh
  ./configure --with-startup=systemd
  make -j8
  sudo make install
  

Note that the Linux RPM and Debian packages do not use the ``/usr/local``
prefix, and files are instead installed to ``/usr/sbin``, and
``/usr/lib``. This difference is a result of aligning with the directory
structure of Linux packaging systems and FreeBSD ports packaging.

Another note is that the Python distutils in Fedora Linux will install the CORE
Python modules to :file:`/usr/lib/python2.7/site-packages/core`, instead of
using the :file:`dist-packages` directory.

The CORE Manual documentation is built separately from the :file:`doc/` 
sub-directory in the source. It requires Sphinx:

.. parsed-literal::

  sudo yum install python-sphinx
  cd core-|version|/doc
  make html
  make latexpdf


.. _Installing_from_Source_on_CentOS:

Installing from Source on CentOS/EL6
------------------------------------

To build CORE from source on CentOS/EL6, first install the `EPEL <http://fedoraproject.org/wiki/EPEL>`_ repo (Extra Packages for Enterprise Linux) in order
to provide the `libev` package.

::

    wget http://dl.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm
    yum localinstall epel-release-6-8.noarch.rpm


Now use the same instructions shown in :ref:`Installing_from_Source_on_Fedora`.
CentOS/EL6 does not use the systemd service file, so the `configure` option
`--with-startup=systemd` should be omitted:

::
    
    ./configure



.. _Installing_from_Source_on_SUSE:

Installing from Source on SUSE
------------------------------

To build CORE from source on SUSE or OpenSUSE, 
use the similar instructions shown in :ref:`Installing_from_Source_on_Fedora`,
except that the following `configure` option should be used:

::
    
    ./configure --with-startup=suse

This causes a separate init script to be installed that is tailored towards SUSE systems.

The `zypper` command is used instead of `yum`.

For OpenSUSE/Xen based installations, refer to the `README-Xen` file included
in the CORE source.


.. _Installing_from_Source_on_FreeBSD:

Installing from Source on FreeBSD
---------------------------------

.. index:: kernel patch

**Rebuilding the FreeBSD Kernel**


The FreeBSD kernel requires a small patch to allow per-node directories in the
filesystem. Also, the `VIMAGE` build option needs to be turned on to enable
jail-based network stack virtualization. The source code for the FreeBSD 
kernel is located in :file:`/usr/src/sys`. 

Instructions below will use the :file:`/usr/src/sys/amd64` architecture 
directory, but the directory :file:`/usr/src/sys/i386` should be substituted
if you are using a 32-bit architecture.

The kernel patch is available from the CORE source tarball under core-|version|/kernel/symlinks-8.1-RELEASE.diff. This patch applies to the
FreeBSD 8.x or 9.x kernels.

.. parsed-literal::

    cd /usr/src/sys
    # first you can check if the patch applies cleanly using the '-C' option
    patch -p1 -C < ~/core-|version|/kernel/symlinks-8.1-RELEASE.diff
    # without '-C' applies the patch
    patch -p1 < ~/core-|version|/kernel/symlinks-8.1-RELEASE.diff
  

A kernel configuration file named :file:`CORE` can be found within the source tarball: core-|version|/kernel/freebsd8-config-CORE. The config is valid for
FreeBSD 8.x or 9.x kernels.

The contents of this configuration file are shown below; you can edit it to suit your needs.

::

  # this is the FreeBSD 9.x kernel configuration file for CORE
  include 	GENERIC
  ident		CORE

  options 	VIMAGE
  nooptions	SCTP
  options	IPSEC
  device	crypto

  options	IPFIREWALL
  options 	IPFIREWALL_DEFAULT_TO_ACCEPT
  

The kernel configuration file can be linked or copied to the kernel source directory. Use it to configure and build the kernel:

.. parsed-literal::

  cd /usr/src/sys/amd64/conf
  cp ~/core-|version|/kernel/freebsd8-config-CORE CORE
  config CORE
  cd ../compile/CORE
  make cleandepend && make depend
  make -j8 && make install
  

Change the number 8 above to match the number of CPU cores you have times two.
Note that the ``make install`` step will move your existing kernel to
``/boot/kernel.old`` and removes that directory if it already exists. Reboot to
enable this new patched kernel.

**Building CORE from Source on FreeBSD**

Here are the prerequisite packages from the FreeBSD ports system:

::

  pkg_add -r tk85
  pkg_add -r libimg
  pkg_add -r bash
  pkg_add -r libev
  pkg_add -r sudo
  pkg_add -r python
  pkg_add -r autotools
  pkg_add -r gmake


Note that if you are installing to a bare FreeBSD system and want to SSH with X11 forwarding to that system, these packages will help:

::

  pkg_add -r xauth
  pkg_add -r xorg-fonts


The ``sudo`` package needs to be configured so a normal user can run the CORE
GUI using the command ``core-gui`` (opening a shell window on a node uses a
command such as ``sudo vimage n1``.)

On FreeBSD, the CORE source is built using autotools and gmake:

.. parsed-literal::

  tar xzf core-|version|.tar.gz
  cd core-|version|
  ./bootstrap.sh
  ./configure
  gmake -j8
  sudo gmake install
  

Build and install the ``vimage`` utility for controlling virtual images. The source can be obtained from `FreeBSD SVN <http://svn.freebsd.org/viewvc/base/head/tools/tools/vimage/>`_, or it is included with the CORE source for convenience:

.. parsed-literal::

  cd core-|version|/kernel/vimage
  make
  make install
  

.. index:: FreeBSD; kernel modules

.. index:: kernel modules

.. index:: ng_wlan and ng_pipe

On FreeBSD you should also install the CORE kernel modules for wireless emulation. Perform this step after you have recompiled and installed FreeBSD kernel.

.. parsed-literal::

  cd core-|version|/kernel/ng_pipe
  make
  sudo make install
  cd ../ng_wlan
  make
  sudo make install
  

The :file:`ng_wlan` kernel module allows for the creation of WLAN nodes. This
is a modified :file:`ng_hub` Netgraph module. Instead of packets being copied
to every connected node, the WLAN maintains a hash table of connected node
pairs. Furthermore, link parameters can be specified for node pairs, in
addition to the on/off connectivity. The parameters are tagged to each packet
and sent to the connected :file:`ng_pipe` module. The :file:`ng_pipe` has been
modified to read any tagged parameters and apply them instead of its default
link effects.

The :file:`ng_wlan` also supports linking together multiple WLANs across different machines using the :file:`ng_ksocket` Netgraph node, for distributed emulation.

The Quagga routing suite is recommended for routing,
:ref:`Quagga_Routing_Software` for installation.

.. _Quagga_Routing_Software:

Quagga Routing Software
=======================

.. index:: Quagga

Virtual networks generally require some form of routing in order to work (e.g.
to automatically populate routing tables for routing packets from one subnet
to another.) CORE builds OSPF routing protocol
configurations by default when the blue router
node type is used. The OSPF protocol is available 
from the `Quagga open source routing suite <http://www.quagga.net>`_. 
Other routing protocols are available using different
node services, :ref:`Default_Services_and_Node_Types`.

Quagga is not specified as a dependency for the CORE packages because 
there are two different Quagga packages that you may use:

* `Quagga <http://www.quagga.net>`_ - the standard version of Quagga, suitable for static wired networks, and usually available via your distribution's package manager.
  .. index:: OSPFv3 MANET

  .. index:: OSPFv3 MDR

  .. index:: MANET Designated Routers (MDR)

* 
  `OSPF MANET Designated Routers <http://www.nrl.navy.mil/itd/ncs/products/ospf-manet>`_ (MDR) - the Quagga routing suite with a modified version of OSPFv3,
  optimized for use with mobile wireless networks. The *mdr* node type (and the MDR service) requires this variant of Quagga.

If you plan on working with wireless networks, we recommend installing OSPF MDR;
otherwise install the standard version of Quagga using your package manager or from source.

.. _Installing_Quagga_from_Packages:

Installing Quagga from Packages
-------------------------------

To install the standard version of Quagga from packages, use your package
manager (Linux) or the ports system (FreeBSD).

Ubuntu users:
::

  sudo apt-get install quagga
  
Fedora users:
::

  yum install quagga
  
FreeBSD users:
::

  pkg_add -r quagga
  

To install the Quagga variant having OSPFv3 MDR, first download the 
appropriate package, and install using the package manager.

Ubuntu users:

.. parsed-literal::

    export URL=http://downloads.pf.itd.nrl.navy.mil/ospf-manet
    wget $URL/|QVER|/|QVERDEB|
    sudo dpkg -i |QVERDEB|

Replace `amd64` with `i686` if using a 32-bit architecture.

Fedora users:

.. parsed-literal::

    export URL=http://downloads.pf.itd.nrl.navy.mil/ospf-manet
    wget $URL/|QVER|/|QVERRPM|
    yum localinstall |QVERRPM|

Replace `x86_64` with `i686` if using a 32-bit architecture.

.. _Compiling_Quagga_for_CORE:

Compiling Quagga for CORE
-------------------------

To compile Quagga to work with CORE on Linux:

.. parsed-literal::

  tar xzf |QVER|.tar.gz
  cd |QVER|
  ./configure --enable-user=root --enable-group=root --with-cflags=-ggdb \\
      --sysconfdir=/usr/local/etc/quagga --enable-vtysh \\
      --localstatedir=/var/run/quagga
  make
  sudo make install
  

Note that the configuration directory :file:`/usr/local/etc/quagga` shown for
Quagga above could be :file:`/etc/quagga`, if you create a symbolic link from
:file:`/etc/quagga/Quagga.conf -> /usr/local/etc/quagga/Quagga.conf` on the
host. The :file:`quaggaboot.sh` script in a Linux network namespace will try and
do this for you if needed.

If you try to run quagga after installing from source and get an error such as:

.. parsed-literal::

  error while loading shared libraries libzebra.so.0

this is usually a sign that you have to run `sudo ldconfig` to refresh the 
cache file.

To compile Quagga to work with CORE on FreeBSD:

.. parsed-literal::

  tar xzf |QVER|.tar.gz
  cd |QVER|
  ./configure --enable-user=root --enable-group=wheel \\
      --sysconfdir=/usr/local/etc/quagga --enable-vtysh \\
      --localstatedir=/var/run/quagga
  gmake
  gmake install
  

On FreeBSD |BSDVERSION| you can use ``make`` or ``gmake``.
You probably want to compile Quagga from the ports system in
:file:`/usr/ports/net/quagga`.

VCORE
=====

.. index:: virtual machines

.. index:: VirtualBox

.. index:: VMware

CORE is capable of running inside of a virtual machine, using
software such as VirtualBox,
VMware Server or QEMU. However, CORE itself is performing machine
virtualization in order to realize multiple emulated nodes, and running CORE
virtually adds additional contention for the physical resources. **For performance reasons, this is not recommended.** Timing inside of a VM often has
problems. If you do run CORE from within a VM, it is recommended that you view
the GUI with remote X11 over SSH, so the virtual machine does not need to
emulate the video card with the X11 application.

.. index:: VCORE

A CORE virtual machine is provided for download, named VCORE.
This is the perhaps the easiest way to get CORE up and running as the machine
is already set up for you. This may be adequate for initially evaluating the
tool but keep in mind the performance limitations of running within VirtualBox
or VMware. To install the virtual machine, you first need to obtain VirtualBox
from http://www.virtualbox.org, or VMware Server or Player from
http://www.vmware.com (this commercial software is distributed for free.)
Once virtualization software has been installed, you can import the virtual
machine appliance using the ``vbox`` file for VirtualBox or the ``vmx`` file for VMware. See the documentation that comes with VCORE for login information.

