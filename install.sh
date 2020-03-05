#!/bin/bash

# exit on error
set -e

function install_python_depencencies() {
  sudo python3 -m pip install -r daemon/requirements.txt
}

function install_ospf_mdr() {
  rm -rf /tmp/ospf-mdr
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

function build_core() {
  ./bootstrap.sh
  ./configure $1
  make -j8
}

function install_core() {
  sudo make install
}

function install_dev_core() {
  cd gui
  sudo make install
  cd -
  cd netns
  sudo make install
  cd -
  cd daemon
}

# detect os/ver for install type
os=""
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  os=${ID}
fi

# parse arguments
while getopts ":d" opt; do
  case ${opt} in
  d)
    dev=1
    ;;
  \?)
    echo "Invalid Option: $OPTARG" 1>&2
    ;;
  esac
done
shift $((OPTIND - 1))

# check install was found
case ${os} in
"ubuntu")
  echo "Installing CORE for Ubuntu"
  echo "installing core system dependencies"
  sudo apt install -y automake pkg-config gcc libev-dev ebtables iproute2 \
    python3.6 python3.6-dev python3-pip python3-tk tk libtk-img ethtool autoconf
  python3 -m pip install grpcio-tools
  echo "installing ospf-mdr system dependencies"
  sudo apt install -y libtool gawk libreadline-dev
  install_ospf_mdr
  if [[ -z ${dev} ]]; then
    echo "normal install"
    install_python_depencencies
    build_core
    install_core
  else
    echo "dev install"
    python3 -m pip install pipenv
    build_core
    install_dev_core
    python3 -m pipenv sync --dev
  fi
  ;;
"centos")
  echo "Installing CORE for CentOS"
  echo "installing core system dependencies"
  sudo yum install -y automake pkgconf-pkg-config gcc gcc-c++ libev-devel iptables-ebtables iproute \
    python36 python36-devel python3-pip python3-tkinter tk ethtool autoconf
  sudo python3 -m pip install grpcio-tools
  echo "installing ospf-mdr system dependencies"
  sudo yum install -y libtool gawk readline-devel
  install_ospf_mdr
  if [[ -z ${dev} ]]; then
    echo "normal install"
    install_python_depencencies
    build_core --prefix=/usr
    install_core
  else
    echo "dev install"
    sudo python3 -m pip install pipenv
    build_core --prefix=/usr
    install_dev_core
    sudo python3 -m pipenv sync --dev
    python3 -m pipenv sync --dev
  fi
  ;;
*)
  echo "unknown OS ID ${os} cannot install"
  ;;
esac
