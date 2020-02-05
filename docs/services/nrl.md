# NRL Services

* Table of Contents
{:toc}

## Overview

The Protean Protocol Prototyping Library (ProtoLib) is a cross-platform library that allows applications to be built while supporting a variety of platforms including Linux, Windows, WinCE/PocketPC, MacOS, FreeBSD, Solaris, etc as well as the simulation environments of NS2 and Opnet. The goal of the Protolib is to provide a set of simple, cross-platform C++ classes that allow development of network protocols and applications that can run on different platforms and in network simulation environments. While Protolib provides an overall framework for developing working protocol implementations, applications, and simulation modules, the individual classes are designed for use as stand-alone components when possible. Although Protolib is principally for research purposes, the code has been constructed to provide robust, efficient performance and adaptability to real applications. In some cases, the code consists of data structures, etc useful in protocol implementations and, in other cases, provides common, cross-platform interfaces to system services and functions (e.g., sockets, timers, routing tables, etc).

Currently the Naval Research Laboratory uses this library to develop a wide variety of protocols.The NRL Protolib currently supports the following protocols:
* MGEN_Sink
* NHDP
* SMF
* OLSR
* OLSRv2
* OLSRORG
* MgenActor
* arouted

## NRL Installation

In order to be able to use the different protocols that NRL offers, you must first download the support library itself. You can get the source code from their [NRL Protolib Repo](https://github.com/USNavalResearchLaboratory/protolib).

## Multi-Generator (MGEN)

Download MGEN from the [NRL MGEN Repo](https://github.com/USNavalResearchLaboratory/mgen), unpack it and copy the protolib library into the main folder *mgen*. Execute the following commands to build the protocol.
```shell
cd mgen/makefiles
make -f Makefile.{os} mgen
```

## Neighborhood Discovery Protocol (NHDP)

Download NHDP from the [NRL NHDP Repo](https://github.com/USNavalResearchLaboratory/NCS-Downloads/tree/master/nhdp).
```shell
sudo apt-get install libpcap-dev libboost-all-dev
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.8.0/protoc-3.8.0-linux-x86_64.zip
unzip protoc-3.8.0-linux-x86_64.zip
```
Then place the binaries in your $PATH. To know your paths you can issue the following command
```shell
echo $PATH
```
Go to the downloaded *NHDP* tarball, unpack it and place the protolib library inside the NHDP main folder. Now, compile the NHDP Protocol.
```shell
cd nhdp/unix
make -f Makefile.{os}
```

## Simplified Multicast Forwarding (SMF)

Download SMF from the [NRL SMF Repo](https://github.com/USNavalResearchLaboratory/nrlsmf) , unpack it and place the protolib library inside the *smf* main folder.
```shell
cd mgen/makefiles
make -f Makefile.{os}
```

## Optimized Link State Routing Protocol (OLSR)

To install the OLSR protocol, download their source code from their [NRL OLSR Repo](https://github.com/USNavalResearchLaboratory/nrlolsr). Unpack it and place the previously downloaded protolib library inside the *nrlolsr* main directory. Then execute the following commands:
```shell
cd ./unix
make -f Makefile.{os}
```
