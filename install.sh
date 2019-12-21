#!/bin/bash

# exit on error
set -e

function install_python_depencencies() {
    sudo python3 -m pip install -r daemon/requirements.txt
}

function install_ospf_mdr() {
    git clone https://github.com/USNavalResearchLaboratory/ospf-mdr /tmp/ospf-mdr
    cd /tmp/ospf-mdr
    ./bootstrap.sh
    ./configure --disable-doc --enable-user=root --enable-group=root --with-cflags=-ggdb \
        --sysconfdir=/usr/local/etc/quagga --enable-vtysh \
        --localstatedir=/var/run/quagga
    make -j8
    sudo make install
    cd -
}

function install_core() {
    ./bootstrap.sh
    ./configure
    make -j8
    sudo make install
}

# detect os/ver for install type
os=""
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    os=${NAME}
fi

# check install was found
case ${os} in
"Ubuntu")
    sudo apt install -y automake pkg-config gcc libev-dev bridge-utils ebtables gawk \
        python3.6 python3.6-dev python3-pip python3-tk tk libtk-img ethtool libtool libreadline-dev autoconf
    install_python_depencencies
    install_ospf_mdr
    install_core
    ;;
"CentOS Linux")
    sudo yum install -y automake pkgconf-pkg-config gcc libev-devel bridge-utils iptables-ebtables gawk \
        python36 python36-devel python3-pip python3-tk tk ethtool libtool readline-devel autoconf
    install_python_depencencies
    install_ospf_mdr
    install_core
    ;;
*)
    echo "unknown os ${os} cannot install"
    ;;
esac
