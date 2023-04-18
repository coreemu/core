# Software Defined Networking

## Overview

Ryu is a component-based software defined networking framework. Ryu provides software components with well defined API
that make it easy for developers to create new network management and control applications. Ryu supports various
protocols for managing network devices, such as OpenFlow, Netconf, OF-config, etc. About OpenFlow, Ryu supports fully
1.0, 1.2, 1.3, 1.4, 1.5 and Nicira Extensions. All of the code is freely available under the Apache 2.0 license.

## Installation

### Prerequisites

```shell
sudo apt-get install gcc python-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev zlib1g-dev
```

### Ryu Package Install

```shell
pip install ryu
```

### Ryu Source Install

```shell
git clone git://github.com/osrg/ryu.git
cd ryu
pip install .
```
