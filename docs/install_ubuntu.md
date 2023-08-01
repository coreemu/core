# Install Ubuntu

## Overview

Below is a detailed path for installing CORE and related tooling on a fresh
Ubuntu 22.04 installation. Both of the examples below will install CORE into its
own virtual environment located at **/opt/core/venv**. Both examples below
also assume using **~/Documents** as the working directory.

## Script Install

This section covers step by step commands that can be used to install CORE using
the script based installation path.

``` shell
# install system packages
sudo apt-get update -y
sudo apt-get install -y ca-certificates git sudo wget tzdata libpcap-dev libpcre3-dev \
    libprotobuf-dev libxml2-dev protobuf-compiler unzip uuid-dev iproute2 iputils-ping \
    tcpdump

# install core
cd ~/Documents
git clone https://github.com/coreemu/core
cd core
./setup.sh
source ~/.bashrc
inv install

# install emane
cd ~/Documents
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.19.6/protoc-3.19.6-linux-x86_64.zip
mkdir protoc
unzip protoc-3.19.6-linux-x86_64.zip -d protoc
git clone https://github.com/adjacentlink/emane.git
cd emane
./autogen.sh
./configure --prefix=/usr
make -j$(nproc)
sudo make install
cd src/python
make clean
PATH=~/Documents/protoc/bin:$PATH make
sudo /opt/core/venv/bin/python -m pip install .
```

## Package Install

This section covers step by step commands that can be used to install CORE using
the package based installation path. This will require downloading a package from the release
page, to use during the install CORE step below.

``` shell
# install system packages
sudo apt-get update -y
sudo apt-get install -y ca-certificates python3 python3-tk python3-pip python3-venv \
    libpcap-dev libpcre3-dev libprotobuf-dev libxml2-dev protobuf-compiler unzip \
    uuid-dev automake gawk git wget libreadline-dev libtool pkg-config g++ make \
    iputils-ping tcpdump

# install core
cd ~/Documents
sudo apt-get install -y ./core_*.deb

# install ospf mdr
cd ~/Documents
git clone https://github.com/USNavalResearchLaboratory/ospf-mdr.git
cd ospf-mdr
./bootstrap.sh
./configure --disable-doc --enable-user=root --enable-group=root \
    --with-cflags=-ggdb --sysconfdir=/usr/local/etc/quagga --enable-vtysh \
    --localstatedir=/var/run/quagga
make -j$(nproc)
sudo make install

# install emane
cd ~/Documents
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.19.6/protoc-3.19.6-linux-x86_64.zip
mkdir protoc
unzip protoc-3.19.6-linux-x86_64.zip -d protoc
git clone https://github.com/adjacentlink/emane.git
cd emane
./autogen.sh
./configure --prefix=/usr
make -j$(nproc)
sudo make install
cd src/python
make clean
PATH=~/Documents/protoc/bin:$PATH make
sudo /opt/core/venv/bin/python -m pip install .
```

## Setup PATH

The CORE virtual environment and related scripts will not be found on your PATH,
so some adjustments needs to be made.

To add support for your user to run scripts from the virtual environment:

```shell
# can add to ~/.bashrc
export PATH=$PATH:/opt/core/venv/bin
```

This will not solve the path issue when running as sudo, so you can do either
of the following to compensate.

```shell
# run command passing in the right PATH to pickup from the user running the command
sudo env PATH=$PATH core-daemon

# add an alias to ~/.bashrc or something similar
alias sudop='sudo env PATH=$PATH'
# now you can run commands like so
sudop core-daemon
```
