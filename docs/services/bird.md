# BIRD Internet Routing Daemon

## Overview

The [BIRD Internet Routing Daemon](https://bird.network.cz/) is a routing
daemon; i.e., a software responsible for managing kernel packet forwarding
tables. It aims to develop a dynamic IP routing daemon with full support of
all modern routing protocols, easy to use configuration interface and powerful
route filtering language, primarily targeted on (but not limited to) Linux and
other UNIX-like systems and distributed under the GNU General Public License.
BIRD has a free implementation of several well known and common routing and
router-supplemental protocols, namely RIP, RIPng, OSPFv2, OSPFv3, BGP, BFD,
and NDP/RA. BIRD supports IPv4 and IPv6 address families, Linux kernel and
several BSD variants (tested on FreeBSD, NetBSD and OpenBSD). BIRD consists
of bird daemon and birdc interactive CLI client used for supervision.

In order to be able to use the BIRD Internet Routing Protocol, you must first
install the project on your machine.

## BIRD Package Install

```shell
sudo apt-get install bird
```

## BIRD Source Code Install

You can download BIRD source code from its
[official repository.](https://gitlab.labs.nic.cz/labs/bird/)

```shell
./configure
make
su
make install
vi /etc/bird/bird.conf
```

The installation will place the bird directory inside */etc* where you will
also find its config file.

In order to be able to do use the Bird Internet Routing Protocol, you must
modify *bird.conf* due to the fact that the given configuration file is not
configured beyond allowing the bird daemon to start, which means that nothing
else will happen if you run it.
