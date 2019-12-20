#!/bin/bash

# exit on error
set -e

# detect os/ver for install type
os=""
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    os=${NAME}
fi

# check install was found
if [[ ${os} == "Ubuntu" ]]; then
    # install system dependencies
    sudo apt install  -y automake pkg-config gcc libev-dev bridge-utils ebtables \
        python3.6 python3.6-dev python3-pip python3-tk tk libtk-img ethtool libtool libreadline-dev autoconf

    # install python dependencies
    sudo python3 -m pip install -r daemon/requirements.txt

    # make and install ospf mdr
    git clone https://github.com/USNavalResearchLaboratory/ospf-mdr /tmp/ospf-mdr
    cd /tmp/ospf-mdr
    ./bootstrap.sh
    ./configure --disable-doc --enable-user=root --enable-group=root --with-cflags=-ggdb \
        --sysconfdir=/usr/local/etc/quagga --enable-vtysh \
        --localstatedir=/var/run/quagga
    make -j8
    sudo make install
    cd -

    # build and install core
    ./bootstrap.sh
    ./configure
    make -j8
    sudo make install
else
    echo "unknown os ${os} cannot install"
fi
