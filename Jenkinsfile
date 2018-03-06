pipeline {
  agent any
  stages {
    stage('build') {
      steps {
        sh './bootstrap.sh'
        sh './configure'
        sh 'make'
        sh 'make install'
      }
    }
    stage('test') {
      steps {
        sh 'pytest'
      }
    }
  }
}