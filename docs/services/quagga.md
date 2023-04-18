# Quagga Routing Suite

## Overview

Quagga is a routing software suite, providing implementations of OSPFv2, OSPFv3, RIP v1 and v2, RIPng and BGP-4 for Unix
platforms, particularly FreeBSD, Linux, Solaris and NetBSD. Quagga is a fork of GNU Zebra which was developed by
Kunihiro Ishiguro.
The Quagga architecture consists of a core daemon, zebra, which acts as an abstraction layer to the underlying Unix
kernel and presents the Zserv API over a Unix or TCP stream to Quagga clients. It is these Zserv clients which typically
implement a routing protocol and communicate routing updates to the zebra daemon.

## Quagga Package Install

```shell
sudo apt-get install quagga
```

## Quagga Source Install

First, download the source code from their [official webpage](https://www.quagga.net/).

```shell
sudo apt-get install gawk
```

Extract the tarball, go to the directory of your currently extracted code and issue the following commands.

```shell
./configure
make
sudo make install
```
