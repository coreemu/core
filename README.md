# CORE [![Codacy Badge](https://api.codacy.com/project/badge/Grade/d94eb0244ade4510a106b4af76077a92)](https://www.codacy.com/app/blakeharnden/core?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=coreemu/core&amp;utm_campaign=Badge_Grade)

CORE: Common Open Research Emulator

Copyright (c)2005-2018 the Boeing Company.

See the LICENSE file included in this distribution.

## About

The Common Open Research Emulator (CORE) is a tool for emulating
networks on one or more machines. You can connect these emulated
networks to live networks. CORE consists of a GUI for drawing
topologies of lightweight virtual machines, and Python modules for
scripting network emulation.

## Documentation and Examples

* Documentation hosted on GitHub
  * <http://coreemu.github.io/core/>
* Basic Script Examples
  * [Examples](daemon/examples/api)
* Custom Service Example
  * [sample.py](daemon/examples/myservices/sample.py)
* Custom Emane Model Example
  * [examplemodel.py](daemon/examples/myemane/examplemodel.py)

## Support

We are leveraging Discord for persistent chat rooms, voice chat, and
GitHub integration. This allows for more dynamic conversations and the
capability to respond faster. Feel free to join us at the link below.
<https://discord.gg/AKd7kmP>

You can also get help with questions, comments, or trouble, by using
the CORE mailing lists:

* [core-users](https://pf.itd.nrl.navy.mil/mailman/listinfo/core-users) for general comments and questions
* [core-dev](https://pf.itd.nrl.navy.mil/mailman/listinfo/core-dev) for bugs, compile errors, and other development issues

## Building CORE

```shell
./bootstrap.sh
./configure
make
sudo make install
```

### Building Documentation

```shell
./bootstrap.sh
./configure
make doc
```

### Building Packages

Install fpm: <http://fpm.readthedocs.io/en/latest/installing.html>

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

### Running CORE

First start the CORE services:

```shell
# sysv
sudo service core-daemon start
# systemd
sudo systemctl start core-daemon
```

This automatically runs the core-daemon program.
Assuming the GUI is in your PATH, run the CORE GUI by typing the following:

```shell
core-gui
```

This launches the CORE GUI. You do not need to run the GUI as root.
