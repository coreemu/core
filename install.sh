#!/bin/bash

# exit on error
set -e

ubuntu_py=3.6
centos_py=36
reinstall=

function install_python_depencencies() {
  sudo python3 -m pip install -r daemon/requirements.txt
}

function install_grpcio_tools() {
  python3 -m pip install --only-binary ":all:" --user grpcio-tools
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

function uninstall_core() {
  sudo make uninstall
  make clean
  ./bootstrap.sh clean
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
while getopts "drv:" opt; do
  case ${opt} in
  d)
    dev=1
    ;;
  v)
    ubuntu_py=${OPTARG}
    centos_py=${OPTARG}
    ;;
  r)
    reinstall=1
    ;;
  \?)
    echo "script usage: $(basename $0) [-d] [-r] [-v python version]" >&2
    exit 1
    ;;
  esac
done
shift $((OPTIND - 1))

# check if we are reinstalling or installing
if [ -z "${reinstall}" ]; then
  echo "installing CORE for ${os}"
  case ${os} in
  "ubuntu")
    echo "installing core system dependencies"
    sudo apt install -y automake pkg-config gcc libev-dev ebtables iproute2 \
      python${ubuntu_py} python${ubuntu_py}-dev python3-pip python3-tk tk libtk-img ethtool autoconf
    install_grpcio_tools
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
      python3 -m pipenv run pre-commit install
    fi
    ;;
  "centos")
    echo "installing core system dependencies"
    sudo yum install -y automake pkgconf-pkg-config gcc gcc-c++ libev-devel iptables-ebtables iproute \
      python${centos_py} python${centos_py}-devel python3-pip python3-tkinter tk ethtool autoconf
    install_grpcio_tools
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
      python3 -m pipenv run pre-commit install
    fi
    ;;
  *)
    echo "unknown OS ID ${os} cannot install"
    ;;
  esac
else
  branch=$(git symbolic-ref --short HEAD)
  echo "reinstalling CORE on ${os} with latest ${branch}"
  echo "uninstalling CORE"
  uninstall_core
  echo "pulling latest code"
  git pull
  echo "installing python dependencies"
  install_python_depencencies
  echo "building CORE"
  case ${os} in
  "ubuntu")
    build_core
    ;;
  "centos")
    build_core --prefix=/usr
    ;;
  *)
    echo "unknown OS ID ${os} cannot reinstall"
    ;;
  esac
  echo "installing CORE"
  install_core
fi
