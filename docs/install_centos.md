# Install CentOS

## Overview

Below is a detailed path for installing CORE and related tooling on a fresh
CentOS 7 install. Both of the examples below will install CORE into its
own virtual environment located at **/opt/core/venv**. Both examples below
also assume using **~/Documents** as the working directory.

## Script Install

This section covers step by step commands that can be used to install CORE using
the script based installation path.

``` shell
# install system packages
sudo yum -y update
sudo yum install -y git sudo wget tzdata unzip libpcap-devel libpcre3-devel \
    libxml2-devel protobuf-devel unzip uuid-devel tcpdump make epel-release
sudo yum-builddep -y python3

# install python3.9
cd ~/Documents
wget https://www.python.org/ftp/python/3.9.15/Python-3.9.15.tgz
tar xf Python-3.9.15.tgz
cd Python-3.9.15
./configure --enable-optimizations --with-ensurepip=install
sudo make -j$(nproc) altinstall
python3.9 -m pip install --upgrade pip

# install core
cd ~/Documents
git clone https://github.com/coreemu/core
cd core
NO_SYSTEM=1 PYTHON=/usr/local/bin/python3.9 ./setup.sh
source ~/.bashrc
PYTHON=python3.9 inv install -p /usr --no-python

# install emane
cd ~/Documents
wget -q https://adjacentlink.com/downloads/emane/emane-1.3.3-release-1.el7.x86_64.tar.gz
tar xf emane-1.3.3-release-1.el7.x86_64.tar.gz
cd emane-1.3.3-release-1/rpms/el7/x86_64
sudo yum install -y ./openstatistic*.rpm ./emane*.rpm ./python3-emane_*.rpm

# install emane python bindings into CORE virtual environment
cd ~/Documents
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.19.6/protoc-3.19.6-linux-x86_64.zip
mkdir protoc
unzip protoc-3.19.6-linux-x86_64.zip -d protoc
git clone https://github.com/adjacentlink/emane.git
cd emane
git checkout v1.3.3
./autogen.sh
PYTHON=/opt/core/venv/bin/python ./configure --prefix=/usr
cd src/python
PATH=~/Documents/protoc/bin:$PATH make
sudo /opt/core/venv/bin/python -m pip install .
```

## Package Install

This section covers step by step commands that can be used to install CORE using
the package based installation path. This will require downloading a package from the release
page, to use during the install CORE step below.

``` shell
# install system packages
sudo yum -y update
sudo yum install -y git sudo wget tzdata unzip libpcap-devel libpcre3-devel libxml2-devel \
    protobuf-devel unzip uuid-devel tcpdump automake gawk libreadline-devel libtool \
    pkg-config make
sudo yum-builddep -y python3

# install python3.9
cd ~/Documents
wget https://www.python.org/ftp/python/3.9.15/Python-3.9.15.tgz
tar xf Python-3.9.15.tgz
cd Python-3.9.15
./configure --enable-optimizations --with-ensurepip=install
sudo make -j$(nproc) altinstall
python3.9 -m pip install --upgrade pip

# install core
cd ~/Documents
sudo PYTHON=python3.9 yum install -y ./core_*.rpm

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
wget -q https://adjacentlink.com/downloads/emane/emane-1.3.3-release-1.el7.x86_64.tar.gz
tar xf emane-1.3.3-release-1.el7.x86_64.tar.gz
cd emane-1.3.3-release-1/rpms/el7/x86_64
sudo yum install -y ./openstatistic*.rpm ./emane*.rpm ./python3-emane_*.rpm

# install emane python bindings into CORE virtual environment
cd ~/Documents
wget https://github.com/protocolbuffers/protobuf/releases/download/v3.19.6/protoc-3.19.6-linux-x86_64.zip
mkdir protoc
unzip protoc-3.19.6-linux-x86_64.zip -d protoc
git clone https://github.com/adjacentlink/emane.git
cd emane
git checkout v1.3.3
./autogen.sh
PYTHON=/opt/core/venv/bin/python ./configure --prefix=/usr
cd src/python
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
