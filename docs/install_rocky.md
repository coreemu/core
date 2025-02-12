# Install Rocky

## Overview

This helps provide an example for installation into a Rocky Linux 8.10
environment. Both of the examples below will install CORE into its
own virtual environment located at **/opt/core/venv**. Both examples below
also assume using **~/Documents** as the working directory.

## Install

This section covers step by step commands that can be used to install CORE using
the package based installation path. This will require downloading a package from the
[release page](https://github.com/coreemu/core/releases), to use during the install CORE step below.

``` shell
# install system packages
sudo dnf -y update
sudo dnf install -y \
    xterm \
    wget \
    tcpdump \
    python3.12 \
    python3.12-tkinter \
    iproute-tc

# install ospf mdr
cd ~/Documents
sudo dnf install -y \
    automake \
    gcc-c++ \
    libtool \
    make \
    pkg-config \
    readline-devel \
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
EMANE_VERSION=1.5.2
EMANE_RELEASE=emane-${EMANE_VERSION}-release-1
EMANE_PACKAGE=${EMANE_RELEASE}.el8.x86_64.tar.gz
wget -q https://adjacentlink.com/downloads/emane/${EMANE_PACKAGE}
tar xf ${EMANE_PACKAGE}
cd ${EMANE_RELEASE}/rpms/el8/x86_64
rm emane-spectrum-tools-*.rpm emane-model-lte*.rpm
rm *devel*.rpm
sudo dnf install -y ./emane*.rpm ./python3-emane-${EMANE_VERSION}-1.el8.noarch.rpm

# install core
cd ~/Documents
CORE_PACKAGE=core_9.2.0_x86_64.rpm
PACKAGE_URL=https://github.com/coreemu/core/releases/latest/download/${CORE_PACKAGE}
wget -q ${PACKAGE_URL}
PYTHON=python3.12 dnf install -y ./${CORE_PACKAGE}

# install emane python bindings into CORE virtual environment
cd ~/Documents
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --set-enabled devel
sudo dnf update -y
sudo dnf install -y \
    protobuf-devel \
    libxml2-devel \
    pcre-devel \
    libuuid-devel \
    libpcap-devel
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.19.6/protoc-3.19.6-linux-x86_64.zip
mkdir protoc
unzip protoc-3.19.6-linux-x86_64.zip -d protoc
git clone https://github.com/adjacentlink/emane.git
cd emane
git checkout v${EMANE_VERSION}
./autogen.sh
PYTHON=/opt/core/venv/bin/python ./configure --prefix=/usr
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
