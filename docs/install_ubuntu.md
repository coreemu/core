# Install Ubuntu

## Overview

Below is a detailed path for installing CORE and related tooling on a fresh
Ubuntu 22.04 installation. Both of the examples below will install CORE into its
own virtual environment located at **/opt/core/venv**. Both examples below
also assume using **~/Documents** as the working directory.

## Install

This section covers step by step commands that can be used to install CORE using
the package based installation path. This will require downloading a package from the
[release page](https://github.com/coreemu/core/releases), to use during the install CORE step below.

``` shell
# install system packages
sudo apt-get update -y
sudo apt-get install -y \
    ca-certificates \
    xterm \
    psmisc \
    python3 \
    python3-tk \
    python3-pip \
    python3-venv \
    wget \
    iproute2 \
    iputils-ping \
    tcpdump

# install ospf mdr
cd ~/Documents
apt-get install -y \
    automake \
    gawk \
    g++ \
    libreadline-dev \
    libtool \
    make \
    pkg-config \
    git
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
EMANE_RELEASE=emane-1.5.1-release-1
EMANE_PACKAGE=${EMANE_RELEASE}.ubuntu-22_04.amd64.tar.gz
wget -q https://adjacentlink.com/downloads/emane/${EMANE_PACKAGE}
tar xf ${EMANE_PACKAGE}
cd ${EMANE_RELEASE}/debs/ubuntu-22_04/amd64
rm emane-spectrum-tools*.deb emane-model-lte*.deb
rm *dev*.deb
sudo apt-get install -y ./emane*.deb ./python3-emane_*.deb

# install core
cd ~/Documents
CORE_PACKAGE=core_9.1.0_amd64.deb
PACKAGE_URL=https://github.com/coreemu/core/releases/latest/download/${CORE_PACKAGE}
wget -q ${PACKAGE_URL}
sudo apt-get install -y ./${CORE_PACKAGE}

# install emane python bindings
cd ~/Documents
sudo apt-get install -y \
    unzip \
    libpcap-dev \
    libpcre3-dev \
    libprotobuf-dev \
    libxml2-dev \
    protobuf-compiler \
    uuid-dev
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.19.6/protoc-3.19.6-linux-x86_64.zip
mkdir protoc
unzip protoc-3.19.6-linux-x86_64.zip -d protoc
git clone https://github.com/adjacentlink/emane.git
cd emane
git checkout v1.5.1
./autogen.sh
./configure --prefix=/usr
cd src/python
PATH=~/Documents/protoc/bin:$PATH make
sudo /opt/core/venv/bin/python -m pip install .
```

## Running CORE

This install will place CORE within a virtual environment, symlinks to CORE scripts will be added to **/usr/bin**.

```shell
# in one terminal run the server daemon
sudo core-daemon
# in another terminal run the gui client
core-gui
```
