# CORE

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
  * http://coreemu.github.io/core/
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
https://discord.gg/AKd7kmP

You can also get help with questions, comments, or trouble, by using
the CORE mailing lists:

* [core-users](https://pf.itd.nrl.navy.mil/mailman/listinfo/core-users) for general comments and questions
* [core-dev](https://pf.itd.nrl.navy.mil/mailman/listinfo/core-dev) for bugs, compile errors, and other development issues

## Building CORE

See [CORE Installation](http://coreemu.github.io/core/install.html) for detailed build instructions

Running CORE
------------

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
