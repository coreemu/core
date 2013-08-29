.. This file is part of the CORE Manual
   (c)2012 the Boeing Company

.. _Performance:

.. include:: constants.txt

***********
Performance
***********

.. index:: performance

.. index:: number of nodes

The top question about the performance of CORE is often
*how many nodes can it handle?* The answer depends on several factors:

* Hardware - the number and speed of processors in the computer, the available
  processor cache, RAM memory, and front-side bus speed may greatly affect
  overall performance.
* Operating system version - Linux or FreeBSD, and the specific kernel versions
  used will affect overall performance.
* Active processes - all nodes share the same CPU resources, so if one or more
  nodes is performing a CPU-intensive task, overall performance will suffer.
* Network traffic - the more packets that are sent around the virtual network
  increases the amount of CPU usage.
* GUI usage - widgets that run periodically, mobility scenarios, and other GUI
  interactions generally consume CPU cycles that may be needed for emulation.

On a typical single-CPU Xeon 3.0GHz server machine with 2GB RAM running FreeBSD
|BSDVERSION|, we have found it reasonable to run 30-75 nodes running
OSPFv2 and OSPFv3 routing. On this hardware CORE can instantiate 100 or more
nodes, but at that point it becomes critical as to what each of the nodes is
doing.

.. index:: network performance

Because this software is primarily a network emulator, the more appropriate
question is *how much network traffic can it handle?* On the same 3.0GHz server
described above, running FreeBSD 4.11, about 300,000 packets-per-second can be
pushed through the system. The number of hops and the size of the packets is
less important. The limiting factor is the number of times that the operating
system needs to handle a packet. The 300,000 pps figure represents the number
of times the system as a whole needed to deal with a packet. As more network
hops are added, this increases the number of context switches and decreases the
throughput seen on the full length of the network path.

.. NOTE::
   The right question to be asking is *"how much traffic?"*,
   not *"how many nodes?"*.

For a more detailed study of performance in CORE, refer to the following publications:

* J\. Ahrenholz, T. Goff, and B. Adamson, Integration of the CORE and EMANE Network Emulators, Proceedings of the IEEE Military Communications Conference 2011, November 2011. 

* Ahrenholz, J., Comparison of CORE Network Emulation Platforms, Proceedings of the IEEE Military Communications Conference 2010, pp. 864-869, November 2010. 

* J\. Ahrenholz, C. Danilov, T. Henderson, and J.H. Kim, CORE: A real-time network emulator, Proceedings of IEEE MILCOM Conference, 2008. 

