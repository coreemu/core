.. This file is part of the CORE Manual
   (c)2012 the Boeing Company

.. _Python_Scripting:

****************
Python Scripting
****************

.. index:: Python scripting

CORE can be used via the :ref:`GUI <Using_the_CORE_GUI>` or Python scripting.
Writing your own Python scripts offers a rich programming
environment with complete control over all aspects of the emulation.
This chapter provides a brief introduction to scripting. Most of the
documentation is available from sample scripts,
or online via interactive Python.

.. index:: sample Python scripts

The best starting point is the sample scripts that are
included with CORE. If you have a CORE source tree, the example script files
can be found under :file:`core/daemon/examples/netns/`. When CORE is installed
from packages, the example script files will be in 
:file:`/usr/share/core/examples/netns/` (or the :file:`/usr/local/...` prefix
when installed from source.) For the most part, the example scripts
are self-documenting; see the comments contained within the Python code. 

The scripts should be run with root privileges because they create new
network namespaces. In general, a CORE Python script does not connect to the
CORE daemon, :file:`core-daemon`; in fact, :file:`core-daemon`
is just another Python script
that uses the CORE Python modules and exchanges messages with the GUI.
To connect the GUI to your scripts, see the included sample scripts that
allow for GUI connections.

Here are the basic elements of a CORE Python script:
::

  #!/usr/bin/python

  from core import pycore

  session = pycore.Session(persistent=True)
  node1 = session.addobj(cls=pycore.nodes.CoreNode, name="n1")
  node2 = session.addobj(cls=pycore.nodes.CoreNode, name="n2")
  hub1 = session.addobj(cls=pycore.nodes.HubNode, name="hub1")
  node1.newnetif(hub1, ["10.0.0.1/24"])
  node2.newnetif(hub1, ["10.0.0.2/24"])

  node1.icmd(["ping", "-c", "5", "10.0.0.2"])
  session.shutdown()
  

The above script creates a CORE session having two nodes connected with a hub.
The first node pings the second node with 5 ping packets; the result is
displayed on screen.

A good way to learn about the CORE Python modules is via interactive Python.
Scripts can be run using *python -i*. Cut and paste the simple script
above and you will have two nodes connected by a hub, with one node running
a test ping to the other.

The CORE Python modules are documented with comments in the code. From an
interactive Python shell, you can retrieve online help about the various
classes and methods; for example *help(pycore.nodes.CoreNode)* or
*help(pycore.Session)*.

An interactive development environment (IDE) is available for browsing
the CORE source, the
`Eric Python IDE <http://eric-ide.python-projects.org/index.html>`_. 
CORE has a project file that can be opened by Eric, in the source under
:file:`core/daemon/CORE.e4p`.
This IDE
has a class browser for viewing a tree of classes and methods. It features
syntax highlighting, auto-completion, indenting, and more. One feature that
is helpful with learning the CORE Python modules is the ability to generate
class diagrams; right-click on a class, choose *Diagrams*, and 
*Class Diagram*.

.. index:: daemon versus script
.. index:: script versus daemon
.. index:: script with GUI support
.. index:: connecting GUI to script

.. NOTE::
   The CORE daemon :file:`core-daemon` manages a list of sessions and allows
   the GUI to connect and control sessions. Your Python script uses the
   same CORE modules but runs independently of the daemon. The daemon
   does not need to be running for your script to work.

The session created by a Python script may be viewed in the GUI if certain
steps are followed. The GUI has a :ref:`File_Menu`, *Execute Python script...* 
option for running a script and automatically connecting to it. Once connected,
normal GUI interaction is possible, such as moving and double-clicking nodes,
activating Widgets, etc.

The script should have a line such as the following for running it from 
the GUI.
::

   if __name__ == "__main__" or __name__ == "__builtin__":
       main()

Also, the script should add its session to the session list after creating it.
A global ``server`` variable is exposed to the script pointing to the
``CoreServer`` object in the :file:`core-daemon`.
::

  def add_to_server(session):
      ''' Add this session to the server's list if this script is executed from
      the core-daemon server.
      '''
      global server
      try:
          server.addsession(session)
          return True
      except NameError:
          return False

::

   session = pycore.Session(persistent=True)
   add_to_server(session)


Finally, nodes and networks need to have their coordinates set to something,
otherwise they will be grouped at the coordinates ``<0, 0>``. First sketching
the topology in the GUI and then using the *Export Python script* option may
help here.
::
   
   switch.setposition(x=80,y=50)


A fully-worked example script that you can launch from the GUI is available
in the file  :file:`switch.py` in the examples directory.
