.. This file is part of the CORE Manual
   (c)2012 the Boeing Company

.. _EMANE:

*****
EMANE
*****

.. index:: EMANE

This chapter describes running CORE with the EMANE emulator.

.. _What_is_EMANE?:

What is EMANE?
==============

.. index:: EMANE; introduction to

The Extendable Mobile Ad-hoc Network Emulator (EMANE) allows heterogeneous
network emulation using a pluggable MAC and PHY layer architecture. The EMANE
framework provides an implementation architecture for modeling different radio
interface types in the form of *Network Emulation Modules* (NEMs) and
incorporating these modules into a real-time emulation running in a distributed
environment.

EMANE is developed by U.S. Naval Research Labs (NRL) Code 5522 and Adjacent
Link LLC,
who maintain these websites:

* `<http://www.nrl.navy.mil/itd/ncs/products/emane>`_
* `<http://www.adjacentlink.com/>`_

Instead of building Linux Ethernet bridging networks with CORE, higher-fidelity
wireless networks can be emulated using EMANE bound to virtual devices. CORE
emulates layers 3 and above (network, session, application) with its virtual
network stacks and process space for protocols and applications, while EMANE
emulates layers 1 and 2 (physical and data link) using its pluggable PHY and
MAC models.

The interface between CORE and EMANE is a TAP device. CORE builds the virtual
node using Linux network namespaces, and installs the TAP device into the
namespace. EMANE binds a userspace socket to the device, on the host before it
is pushed into the namespace, for sending and receiving data. The *Virtual
Transport* is the EMANE component responsible for connecting with the TAP
device.

EMANE models are configured through CORE's WLAN configuration dialog.  A
corresponding EmaneModel Python class is sub-classed for each supported EMANE
model, to provide configuration items and their mapping to XML files. This way
new models can be easily supported. When CORE starts the emulation, it
generates the appropriate XML files that specify the EMANE NEM configuration,
and launches the EMANE daemons.

Some EMANE models support location information to determine when packets should
be dropped. EMANE has an event system where location events are broadcast to
all NEMs. CORE can generate these location events when nodes are moved on the
canvas. The canvas size and scale dialog has controls for mapping the X,Y
coordinate system to a latitude, longitude geographic system that EMANE uses.
When specified in the :file:`core.conf` configuration file, CORE can also
subscribe to EMANE location events and move the nodes on the canvas as they are
moved in the EMANE emulation. This would occur when an Emulation Script
Generator, for example, is running a mobility script.

.. index:: EMANE; Configuration

.. index:: EMANE; Installation

.. _EMANE_Configuration:

EMANE Configuration
===================


CORE and EMANE currently work together only on the Linux network namespaces
platform. The normal CORE installation instructions should be followed from
:ref:`Installation`.

The CORE configuration file :file:`/etc/core/core.conf` has options specific to
EMANE. Namely, the `emane_models` line contains a comma-separated list of EMANE
models that will be available. Each model has a corresponding Python file
containing the *EmaneModel* subclass. A portion of the default
:file:`core.conf` file is shown below:

::

  # EMANE configuration
  emane_platform_port = 8101
  emane_transform_port = 8201
  emane_event_monitor = False
  emane_models = RfPipe, Ieee80211abg
  

EMANE can be installed from deb or RPM packages or from source. See the 
`EMANE website <http://www.nrl.navy.mil/itd/ncs/products/emane>`_ for 
full details. 

Here are quick instructions for installing all EMANE packages:

::

  # install dependencies
  sudo apt-get install libssl-dev libxml-lixbml-perl libxml-simple-perl
  # download and install EMANE 0.8.1
  export URL=http://downloads.pf.itd.nrl.navy.mil/emane/0.8.1-r2
  wget $URL/emane-0.8.1-release-2.ubuntu-12_04.amd64.tgz
  tar xzf emane-0.8.1-release-2.ubuntu-12_04.amd64.tgz
  sudo dpkg -i emane-0.8.1-release-2/deb/ubuntu-12_04/amd64/*.deb
  

If you have an EMANE event generator (e.g. mobility or pathloss scripts) and
want to have CORE subscribe to EMANE location events, set the following line in
the :file:`/etc/core/core.conf` configuration file:
::

  emane_event_monitor = True
  
Do not set the above option to True if you want to manually drag nodes around
on the canvas to update their location in EMANE.

Another common issue is if installing EMANE from source, the default configure
prefix will place the DTD files in :file:`/usr/local/share/emane/dtd` while
CORE expects them in :file:`/usr/share/emane/dtd`. A symbolic link will fix
this:
::

  sudo ln -s /usr/local/share/emane /usr/share/emane
  

.. _Single_PC_with_EMANE:

Single PC with EMANE
====================

This section describes running CORE and EMANE on a single machine. This is the
default mode of operation when building an EMANE network with CORE. The OTA
manager interface is off and the virtual nodes use the loopback device for
communicating with one another. This prevents your emulation session from
sending data on your local network and interfering with other EMANE users.

EMANE is configured through a WLAN node, because it is all about emulating
wireless radio networks. Once a node is linked to a WLAN cloud configured with
an EMANE model, the radio interface on that node may also be configured
separately (apart from the cloud.)

Double-click on a WLAN node to invoke the WLAN configuration dialog. Click the 
*EMANE* tab; when EMANE has
been properly installed, EMANE wireless modules should be listed in the 
*EMANE Models* list. (You may need to restart the CORE daemon if
it was running prior to installing the EMANE Python bindings.) 
Click on a model name to enable it.

When an EMANE model is selected in the *EMANE Models* list, clicking on
the *model options* button causes the GUI to query the CORE daemon for
configuration items. Each model will have different parameters, refer to the
EMANE documentation for an explanation of each item. The defaults values are
presented in the dialog. Clicking *Apply*  and *Apply* again will store
the EMANE model selections.

The *EMANE options* button
allows specifying some global parameters for EMANE, some of
which are necessary for distributed operation, see :ref:`Distributed_EMANE`. 

.. index:: RF-PIPE model

.. index:: 802.11 model

.. index:: ieee80211abg model

.. index:: geographic location

.. index:: Universal PHY

The RF-PIPE and IEEE 802.11abg models use a Universal PHY that supports
geographic location information for determining pathloss between nodes. A
default latitude and longitude location is provided by CORE and this
location-based pathloss is enabled by default; this is the *pathloss mode*
setting for the Universal PHY.  Moving a node on the canvas while the emulation
is running generates location events for EMANE. To view or change the
geographic location or scale of the canvas use the *Canvas Size and Scale*
dialog available from the *Canvas* menu.

.. index:: UTM zones

.. index:: UTM projection

Note that conversion between geographic and Cartesian
coordinate systems is done using UTM 
(Universal Transverse Mercator) projection, where
different zones of 6 degree longitude bands are defined.
The location events generated by
CORE may become inaccurate near the zone boundaries for very large scenarios 
that span multiple UTM zones. It is recommended that EMANE location scripts
be used to achieve geo-location accuracy in this situation.

Clicking the green *Start* button launches the emulation and causes TAP 
devices to be created in the virtual nodes that are linked to the EMANE WLAN.
These devices appear with interface names such as eth0, eth1, etc. The EMANE
daemons should now be running on the host:
::

  > ps -aef | grep emane
  root   10472   1  1 12:57 ?   00:00:00 emane --logl 0 platform.xml
  root   10526   1  1 12:57 ?   00:00:00 emanetransportd --logl 0 tr
  
The above example shows the *emane* and *emanetransportd* daemons started by
CORE. To view the configuration generated by CORE, look in the
:file:`/tmp/pycore.nnnnn/` session directory for a :file:`platform.xml` file
and other XML files. One easy way to view this information is by
double-clicking one of the virtual nodes, and typing *cd ..* in the shell to go
up to the session directory.

When EMANE is used to network together CORE nodes, no Ethernet bridging device
is used. The Virtual Transport creates a TAP device that is installed into the
network namespace container, so no corresponding device is visible on the host.

.. index:: Distributed_EMANE
.. _Distributed_EMANE:

Distributed EMANE
=================


Running CORE and EMANE distributed among two or more emulation servers is
similar to running on a single machine. There are a few key configuration items
that need to be set in order to be successful, and those are outlined here.

Because EMANE uses a multicast channel to disseminate data to all NEMs, it is
a good idea to maintain separate networks for data and control. The control
network may be a shared laboratory network, for example, but you do not want
multicast traffic on the data network to interfere with other EMANE users.
The examples described here will use *eth0* as a control interface
and *eth1* as a data interface, although using separate interfaces
is not strictly required. Note that these interface names refer to interfaces
present on the host machine, not virtual interfaces within a node.

Each machine that will act as an emulation server needs to have CORE and EMANE 
installed. Refer to the :ref:`Distributed_Emulation` section for configuring
CORE.

The IP addresses of the available servers are configured from the 
CORE emulation servers dialog box (choose *Session* then 
*Emulation servers...*) described in :ref:`Distributed_Emulation`. 
This list of servers is stored in a :file:`~/.core/servers.conf` file.
The dialog shows available servers, some or all of which may be
assigned to nodes on the canvas.

Nodes need to be assigned to emulation servers as described in 
:ref:`Distributed_Emulation`. Select several nodes, right-click them, and
choose *Assign to* and the name of the desired server. When a node is not
assigned to any emulation server, it will be emulated locally. The local
machine that the GUI connects with is considered the "master" machine, which in
turn connects to the other emulation server "slaves". Public key SSH should
be configured from the master to the slaves as mentioned in the 
:ref:`Distributed_Emulation` section.

The EMANE models can be configured as described in :ref:`Single_PC_with_EMANE`.
Under the *EMANE* tab of the EMANE WLAN, click on the *EMANE options* button.
This brings
up the emane configuration dialog. The *enable OTA Manager channel* should
be set to *on*. The *OTA Manager device* and *Event Service device* should
be set to something other than the loopback *lo* device. For example, if eth0
is your control device and eth1 is for data, set the OTA Manager device to eth1
and the Event Service device to eth0. Click *Apply* to
save these settings.

.. HINT::
   Here is a quick checklist for distributed emulation with EMANE.

   1. Follow the steps outlined for normal CORE :ref:`Distributed_Emulation`.
   2. Under the *EMANE* tab of the EMANE WLAN, click on *EMANE options*.
   3. Turn on the *OTA Manager channel* and set the *OTA Manager device*.
      Also set the *Event Service device*.
   4. Select groups of nodes, right-click them, and assign them to servers
      using the *Assign to* menu.
   5. Synchronize your machine's clocks prior to starting the emulation,
      using ``ntp`` or ``ptp``. Some EMANE models are sensitive to timing.
   6. Press the *Start* button to launch the distributed emulation.


Now when the Start button is used to instantiate the emulation, 
the local CORE Python
daemon will connect to other emulation servers that have been assigned to nodes.
Each server will have its own session directory where the :file:`platform.xml`
file and other EMANE XML files are generated. The NEM IDs are automatically
coordinated across servers so there is no overlap. Each server also gets its
own Platform ID.

Instead of using the loopback device for disseminating multicast
EMANE events, an Ethernet device is used as specified in the
*configure emane* dialog.
EMANE's Event Service can be run with mobility or pathloss scripts
as described in
:ref:`Single_PC_with_EMANE`. If CORE is not subscribed to location events, it
will generate them as nodes are moved on the canvas. 

Double-clicking on a node during runtime will cause the GUI to attempt to SSH
to the emulation server for that node and run an interactive shell. The public
key SSH configuration should be tested with all emulation servers prior to
starting the emulation.


