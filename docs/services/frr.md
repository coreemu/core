# FRRouting

* Table of Contents
{:toc}

## Overview

FRRouting is a routing software package that provides TCP/IP based routing services with routing protocols support such as BGP, RIP, OSPF, IS-IS and more. FRR also supports special BGP Route Reflector and Route Server behavior. In addition to traditional IPv4 routing protocols, FRR also supports IPv6 routing protocols. With an SNMP daemon that supports the AgentX protocol, FRR provides routing protocol MIB read-only access (SNMP Support).

FRR (as of v7.2) currently supports the following protocols:
* BGPv4
* OSPFv2
* OSPFv3
* RIPv1/v2/ng
* IS-IS
* PIM-SM/MSDP/BSM(AutoRP)
* LDP
* BFD
* Babel
* PBR
* OpenFabric
* VRRPv2/v3
* EIGRP (alpha)
* NHRP (alpha)

## FRRouting Package Install

Ubuntu 19.10 and later
```shell
sudo apt update && sudo apt install frr
```

Ubuntu 16.04 and Ubuntu 18.04
```shell
sudo apt install curl
curl -s https://deb.frrouting.org/frr/keys.asc | sudo apt-key add -
FRRVER="frr-stable"
echo deb https://deb.frrouting.org/frr $(lsb_release -s -c) $FRRVER | sudo tee -a /etc/apt/sources.list.d/frr.list
sudo apt update && sudo apt install frr frr-pythontools
```
Fedora 31
```shell
sudo dnf update && sudo dnf install frr
```

## FRRouting Source Code Install

Building FRR from source is the best way to ensure you have the latest features and bug fixes. Details for each supported platform, including dependency package listings, permissions, and other gotchas, are in the developer’s documentation.

FRR’s source is available on the project [GitHub page](https://github.com/FRRouting/frr).
```shell
git clone https://github.com/FRRouting/frr.git
```

Change into your FRR source directory and issue:
```shell
./bootstrap.sh
```
Then, choose the configuration options that you wish to use for the installation. You can find these options on FRR's [official webpage](http://docs.frrouting.org/en/latest/installation.html). Once you have chosen your configure options, run the configure script and pass the options you chose:
```shell
./configure \
    --prefix=/usr \
    --enable-exampledir=/usr/share/doc/frr/examples/ \
    --localstatedir=/var/run/frr \
    --sbindir=/usr/lib/frr \
    --sysconfdir=/etc/frr \
    --enable-pimd \
    --enable-watchfrr \
    ...
```
After configuring the software, you are ready to build and install it in your system.
```shell
make && sudo make install
```
If everything finishes successfully, FRR should be installed.
