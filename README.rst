====
CORE
====

CORE: Common Open Research Emulator

Copyright (c)2005-2013 the Boeing Company.

See the LICENSE file included in this distribution.

About
=====

CORE is a tool for emulating networks using a GUI or Python scripts. The CORE
project site (1) is a good source of introductory information, with a manual,
screenshots, and demos about this software. The GitHub project (2) hosts the
source repos, wiki, and bug tracker. There is a deprecated
Google Code page (3) with the old wiki, blog, bug tracker, and quickstart guide.

1. http://www.nrl.navy.mil/itd/ncs/products/core

2. https://github.com/coreemu/core

3. http://code.google.com/p/coreemu/

4. `Official Documentation`_

.. _Official Documentation: https://downloads.pf.itd.nrl.navy.mil/docs/core/core-html/index.html


Building CORE
=============

To build this software you should use:

    ./bootstrap.sh
    ./configure
    make
    sudo make install

Here is what is installed with 'make install':

    /usr/local/bin/core-gui
    /usr/local/sbin/core-daemon
    /usr/local/sbin/[vcmd, vnoded, coresendmsg, core-cleanup.sh]
    /usr/local/lib/core/*
    /usr/local/share/core/*
    /usr/local/lib/python2.6/dist-packages/core/*
    /usr/local/lib/python2.6/dist-packages/[netns,vcmd].so
    /etc/core/*
    /etc/init.d/core

See the manual for the software required for building CORE.


Running CORE
============

First start the CORE services:

    sudo /etc/init.d/core-daemon start

This automatically runs the core-daemon program. 
Assuming the GUI is in your PATH, run the CORE GUI by typing the following:

    core-gui

This launches the CORE GUI. You do not need to run the GUI as root.


Support
=======

If you have questions, comments, or trouble, please use the CORE mailing lists:

- `core-users`_ for general comments and questions

- `core-dev`_ for bugs, compile errors, and other development issues


.. _core-users: https://pf.itd.nrl.navy.mil/mailman/listinfo/core-users
.. _core-dev: https://pf.itd.nrl.navy.mil/mailman/listinfo/core-dev


