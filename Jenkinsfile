pipeline {
  agent any
  stages {
    stage('install dependencies') {
      steps {
        sh 'sudo apt-get install libev-dev bridge-utils ebtables libtk-img bash iproute python tcl8.5 tk8.5 autoconf automake gcc libev-dev make python-dev libreadline-dev pkg-config imagemagick help2man python-sphinx python-setuptools python-pip'
        sh 'sudo pip install mock pytest pytest-runner'
      }
    }
    stage('build core') {
      steps {
        sh './bootstrap.sh'
        sh './configure'
        sh 'make'
        sh 'sudo make install'
      }
    }
    stage('test core') {
      steps {
        sh 'pytest daemon/tests'
      }
    }
  }
}