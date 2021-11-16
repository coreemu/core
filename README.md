# CORE

CORE: Common Open Research Emulator

Copyright (c)2005-2021 the Boeing Company.

See the LICENSE file included in this distribution.

## About

The Common Open Research Emulator (CORE) is a tool for emulating
networks on one or more machines. You can connect these emulated
networks to live networks. CORE consists of a GUI for drawing
topologies of lightweight virtual machines, and Python modules for
scripting network emulation.

## Quick Start

The following should get you up and running on Ubuntu 18+ and CentOS 7+
from a clean install, it will prompt you for sudo password. This would
install CORE into a python3 virtual environment and install
[OSPF MDR](https://github.com/USNavalResearchLaboratory/ospf-mdr) from source.
For more details on installation see [here](https://coreemu.github.io/core/install.html).

```shell
git clone https://github.com/coreemu/core.git
cd core
```

Ubuntu:
```shell
./install.sh
```

CentOS:
```shell
./install.sh -p /usr
```

To additionally install EMANE:
```shell
reset
inv install-emane
```

## Documentation & Support

We are leveraging GitHub hosted documentation and Discord for persistent
chat rooms. This allows for more dynamic conversations and the
capability to respond faster. Feel free to join us at the link below.

* [Documentation](https://coreemu.github.io/core/)
* [Discord Channel](https://discord.gg/AKd7kmP)
