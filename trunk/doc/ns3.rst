.. This file is part of the CORE Manual
   (c)2012-2013 the Boeing Company

.. _ns-3:

****
ns-3
****

.. index:: ns-3

This chapter describes running CORE with the 
`ns-3 network simulator <http://www.nsnam.org>`_.

.. _What_is_ns-3?:

What is ns-3?
=============

.. index:: ns-3 Introduction

ns-3 is a discrete-event network simulator for Internet systems, targeted primarily for research and educational use. [#f1]_ By default, ns-3 simulates entire networks, from applications down to channels, and it does so in simulated time, instead of real (wall-clock) time.

CORE can run in conjunction with ns-3 to simulate some types of networks.  CORE
network namespace virtual nodes can have virtual TAP interfaces installed using
the simulator for communication. The simulator needs to run at wall clock time
with the real-time scheduler.  In this type of configuration, the CORE
namespaces are used to provide packets to the ns-3 devices and channels.
This allows, for example, wireless models developed for ns-3 to be used
in an emulation context.

Users simulate networks with ns-3 by writing C++ programs or Python scripts that
import the ns-3 library. Simulation models are objects instantiated in these
scripts. Combining the CORE Python modules with ns-3 Python bindings allow
a script to easily set up and manage an emulation + simulation environment.

.. rubric:: Footnotes
.. [#f1] http://www.nsnam.org

.. _ns-3_Scripting:

ns-3 Scripting
==============

.. index:: ns-3 scripting

Currently, ns-3 is supported by writing
:ref:`Python scripts <Python_Scripting>`, but not through
drag-and-drop actions within the GUI.
If you have a copy of the CORE source, look under :file:`core/daemon/ns3/examples/` for example scripts; a CORE installation package puts these under
:file:`/usr/share/core/examples/corens3`.

To run these scripts, install CORE so the CORE Python libraries are accessible,
and download and build ns-3. This has been tested using ns-3 releases starting
with 3.11 (and through 3.16 as of this writing).  

The first step is to open an ns-3 waf shell.  `waf <http://code.google.com/p/waf/>`_ is the build system for ns-3.  Opening a waf shell as root will merely
set some environment variables useful for finding python modules and ns-3
executables.  The following environment variables are extended or set by
issuing `waf shell`:

::

  PATH
  PYTHONPATH
  LD_LIBRARY_PATH
  NS3_MODULE_PATH
  NS3_EXECUTABLE_PATH

Open a waf shell as root, so that network namespaces may be instantiated
by the script with root permissions.  For an example, run the
:file:`ns3wifi.py` 
program, which simply instantiates 10 nodes (by default) and places them on 
an ns-3 WiFi channel.  That is, the script will instantiate 10 namespace nodes,
and create a special tap device that sends packets between the namespace
node and a special ns-3 simulation node, where the tap device is bridged
to an ns-3 WiFi network device, and attached to an ns-3 WiFi channel.  

::

  > cd ns-allinone-3.16/ns-3.16
  > sudo ./waf shell
  # # use '/usr/local' below if installed from source
  # cd /usr/share/core/examples/corens3/
  # python -i ns3wifi.py
  running ns-3 simulation for 600 seconds

  >>> print session
  <corens3.obj.Ns3Session object at 0x1963e50>
  >>>
  

The interactive Python shell allows some interaction with the Python objects
for the emulation.

In another terminal, nodes can be accessed using *vcmd*:
::

  vcmd -c /tmp/pycore.10781/n1 -- bash
  root@n1:/tmp/pycore.10781/n1.conf#
  root@n1:/tmp/pycore.10781/n1.conf# ping 10.0.0.3
  PING 10.0.0.3 (10.0.0.3) 56(84) bytes of data.
  64 bytes from 10.0.0.3: icmp_req=1 ttl=64 time=7.99 ms
  64 bytes from 10.0.0.3: icmp_req=2 ttl=64 time=3.73 ms
  64 bytes from 10.0.0.3: icmp_req=3 ttl=64 time=3.60 ms
  ^C
  --- 10.0.0.3 ping statistics ---
  3 packets transmitted, 3 received, 0% packet loss, time 2002ms
  rtt min/avg/max/mdev = 3.603/5.111/7.993/2.038 ms
  root@n1:/tmp/pycore.10781/n1.conf# 
  

The ping packets shown above are traversing an ns-3 ad-hoc Wifi simulated 
network.

To clean up the session, use the Session.shutdown() method from the Python
terminal.

::

  >>> print session
  <corens3.obj.Ns3Session object at 0x1963e50>
  >>>
  >>> session.shutdown()
  >>>
  

A CORE/ns-3 Python script will instantiate an Ns3Session, which is a 
CORE Session
having CoreNs3Nodes, an ns-3 MobilityHelper, and a fixed duration. 
The CoreNs3Node inherits from both the CoreNode and the ns-3 Node classes -- it
is a network namespace having an associated simulator object. The CORE TunTap
interface is used, represented by a ns-3 TapBridge in `CONFIGURE_LOCAL`
mode, where ns-3 creates and configures the tap device. An event is scheduled
to install the taps at time 0.

.. NOTE::
   The GUI can be used to run the :file:`ns3wifi.py`
   and :file:`ns3wifirandomwalk.py` scripts directly. First, ``core-daemon``
   must be
   stopped and run within the waf root shell. Then the GUI may be run as
   a normal user, and the *Execute Python Script...* option may be used from
   the *File* menu. Dragging nodes around in the :file:`ns3wifi.py` example
   will cause their ns-3 positions to be updated.


Users may find the files :file:`ns3wimax.py` and :file:`ns3lte.py` 
in that example
directory; those files were similarly configured, but the underlying
ns-3 support is not present as of ns-3.16, so they will not work.  Specifically,
the ns-3 has to be extended to support bridging the Tap device to
an LTE and a WiMax device.

.. _ns-3_Integration_details:

Integration details
===================

.. index:: ns-3 integration details

The previous example :file:`ns3wifi.py` used Python API from the special Python
objects *Ns3Session* and *Ns3WifiNet*.  The example program does not import
anything directly from the ns-3 python modules; rather, only the above
two objects are used, and the API available to configure the underlying
ns-3 objects is constrained.  For example, *Ns3WifiNet* instantiates 
a constant-rate 802.11a-based ad hoc network, using a lot of ns-3 defaults.

However, programs may be written with a blend of ns-3 API and CORE Python
API calls.  This section examines some of the fundamental objects in
the CORE ns-3 support.  Source code can be found in 
:file:`daemon/ns3/corens3/obj.py` and example
code in :file:`daemon/ns3/corens3/examples/`.

Ns3Session
----------

The *Ns3Session* class is a CORE Session that starts an ns-3 simulation
thread.  ns-3 actually runs as a separate process on the same host as
the CORE daemon, and the control of starting and stopping this process
is performed by the *Ns3Session* class.

Example:

::

    session = Ns3Session(persistent=True, duration=opt.duration)

Note the use of the duration attribute to control how long the ns-3 simulation
should run.  By default, the duration is 600 seconds.

Typically, the session keeps track of the ns-3 nodes (holding a node
container for references to the nodes).  This is accomplished via the
`addnode()` method, e.g.:

::

    for i in xrange(1, opt.numnodes + 1):
      node = session.addnode(name = "n%d" % i)

`addnode()` creates instances of a *CoreNs3Node*, which we'll cover next.

CoreNs3Node
-----------

A *CoreNs3Node* is both a CoreNode and an ns-3 node:

::
  
   class CoreNs3Node(CoreNode, ns.network.Node):
       ''' The CoreNs3Node is both a CoreNode backed by a network namespace and
       an ns-3 Node simulator object. When linked to simulated networks, the TunTap
       device will be used.


CoreNs3Net
-----------

A *CoreNs3Net* derives from *PyCoreNet*.  This network exists entirely
in simulation, using the TunTap device to interact between the emulated
and the simulated realm.  *Ns3WifiNet* is a specialization of this.

As an example, this type of code would be typically used to add a WiFi
network to a session:

::

    wifi = session.addobj(cls=Ns3WifiNet, name="wlan1", rate="OfdmRate12Mbps")
    wifi.setposition(30, 30, 0)

The above two lines will create a wlan1 object and set its initial canvas
position.  Later in the code, the newnetif method of the CoreNs3Node can
be used to add interfaces on particular nodes to this network; e.g.:

::

    for i in xrange(1, opt.numnodes + 1):
        node = session.addnode(name = "n%d" % i)
        node.newnetif(wifi, ["%s/%s" % (prefix.addr(i), prefix.prefixlen)])


.. _ns-3_Mobility:

Mobility
========

.. index:: ns-3 mobility

Mobility in ns-3 is handled by an object (a MobilityModel) aggregated to
an ns-3 node.  The MobilityModel is able to report the position of the
object in the ns-3 space.  This is a slightly different model from, for 
instance, EMANE, where location is associated with an interface, and the
CORE GUI, where mobility is configured by right-clicking on a WiFi
cloud.

The CORE GUI supports the ability to render the underlying ns-3 mobility
model, if one is configured, on the CORE canvas.  For example, the 
example program :file:`ns3wifirandomwalk.py` uses five nodes (by default) in
a random walk mobility model.  This can be executed by starting the
core daemon from an ns-3 waf shell:

::

   # sudo bash
   # cd /path/to/ns-3
   # ./waf shell
   # core-daemon

and in a separate window, starting the CORE GUI (not from a waf shell)
and selecting the
*Execute Python script...* option from the File menu, selecting the
:file:`ns3wifirandomwalk.py` script.

The program invokes ns-3 mobility through the following statement:

::

    session.setuprandomwalkmobility(bounds=(1000.0, 750.0, 0))

This can be replaced by a different mode of mobility, in which nodes
are placed according to a constant mobility model, and a special
API call to the CoreNs3Net object is made to use the CORE canvas
positions.

::

    -    session.setuprandomwalkmobility(bounds=(1000.0, 750.0, 0))
    +    session.setupconstantmobility()
    +    wifi.usecorepositions()


In this mode, the user dragging around the nodes on the canvas will
cause CORE to update the position of the underlying ns-3 nodes. 


.. _ns-3_Under_Development:

Under Development
=================

.. index:: limitations with ns-3

Support for ns-3 is fairly new and still under active development.
Improved support may be found in the development snapshots available on the web.

The following limitations will be addressed in future releases:

* GUI configuration and control - currently ns-3 networks can only be
  instantiated from a Python script or from the GUI hooks facility.

* Model support - currently the WiFi model is supported. The WiMAX and 3GPP LTE
  models have been experimented with, but are not currently working with the
  TapBridge device.


