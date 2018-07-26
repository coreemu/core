pipeline {
  agent any
  stages {
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
        sh 'pytest daemon/tests/test_core.py'
        sh 'pytest daemon/tests/test_gui.py'
        sh 'pytest daemon/tests/test_emane.py'
      }
    }
  }
}