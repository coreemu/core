# Utility Services

* Table of Contents
{:toc}

# Overview

Variety of convenience services for carrying out common networking changes.

The following services are provided as utilities:
* UCARP
* IP Forward
* Default Routing
* Default Muticast Routing
* Static Routing
* SSH
* DHCP
* DHCP Client
* FTP
* HTTP
* PCAP
* RADVD
* ATD

## Installation

To install the functionality of the previously metioned services you can run the following command:
```shell
sudo apt-get install isc-dhcp-server apache2 libpcap-dev radvd at
```

## UCARP

UCARP allows a couple of hosts to share common virtual IP addresses in order to provide automatic failover. It is a portable userland implementation of the secure and patent-free Common Address Redundancy Protocol (CARP, OpenBSD's alternative to the patents-bloated VRRP).

Strong points of the CARP protocol are: very low overhead, cryptographically signed messages, interoperability between different operating systems and no need for any dedicated extra network link between redundant hosts.

### Installation

```shell
sudo apt-get install ucarp
```
