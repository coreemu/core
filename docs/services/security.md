# Security Services

## Overview

The security services offer a wide variety of protocols capable of satisfying the most use cases available. Security
services such as IP security protocols, for providing security at the IP layer, as well as the suite of protocols
designed to provide that security, through authentication and encryption of IP network packets. Virtual Private
Networks (VPNs) and Firewalls are also available for use to the user.

## Installation

Libraries needed for some security services.

```shell
sudo apt-get install ipsec-tools racoon
```

## OpenVPN

Below is a set of instruction for running a very simple OpenVPN client/server scenario.

### Installation

```shell
# install openvpn
sudo apt install openvpn

# retrieve easyrsa3 for key/cert generation
git clone https://github.com/OpenVPN/easy-rsa
```

### Generating Keys/Certs

```shell
# navigate into easyrsa3 repo subdirectory that contains built binary
cd easy-rsa/easyrsa3

# initalize pki
./easyrsa init-pki

# build ca
./easyrsa build-ca

# generate and sign server keypair(s)
SERVER_NAME=server1
./easyrsa get-req $SERVER_NAME nopass
./easyrsa sign-req server $SERVER_NAME

# generate and sign client keypair(s)
CLIENT_NAME=client1
./easyrsa get-req $CLIENT_NAME nopass
./easyrsa sign-req client $CLIENT_NAME

# DH generation
./easyrsa gen-dh

# create directory for keys for CORE to use
# NOTE: the default is set to a directory that requires using sudo, but can be
# anywhere and not require sudo at all
KEYDIR=/etc/core/keys
sudo mkdir $KEYDIR

# move keys to directory
sudo cp pki/ca.crt $KEYDIR
sudo cp pki/issued/*.crt $KEYDIR
sudo cp pki/private/*.key $KEYDIR
sudo cp pki/dh.pem $KEYDIR/dh1024.pem
```

### Configure Server Nodes

Add VPNServer service to nodes desired for running an OpenVPN server.

Modify [sampleVPNServer](https://github.com/coreemu/core/blob/master/package/examples/services/sampleVPNServer) for the
following

* Edit keydir key/cert directory
* Edit keyname to use generated server name above
* Edit vpnserver to match an address that the server node will have

### Configure Client Nodes

Add VPNClient service to nodes desired for acting as an OpenVPN client.

Modify [sampleVPNClient](https://github.com/coreemu/core/blob/master/package/examples/services/sampleVPNClient) for the
following

* Edit keydir key/cert directory
* Edit keyname to use generated client name above
* Edit vpnserver to match the address a server was configured to use
