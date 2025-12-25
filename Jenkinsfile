pipeline {
    agent any

    parameters {
        choice(name: 'ACTION', choices: ['Deploy New Version', 'Test Only'], description: 'Choose action')
        string(name: 'VERSION_TAG', defaultValue: 'v1.0.0', description: 'Tag for the Docker Image')
        string(name: 'APP_COLOR', defaultValue: '#e0f7fa', description: 'Hex Color for App Background')
    }

    environment {
        // Configuration
        NEXUS_REGISTRY = "registry.nchldemo.com"
        NEXUS_CRED     = "nexus-auth"      // ID of Jenkins Credential
        IMAGE_NAME     = "fintech-python-app-gg" // Add your name here
        CONTAINER_NAME = "fintech-prod-container-gg" // Add your name here
        
        // ZAP Configuration
        ZAP_PORT       = "9000" // Change the port
        
        // Map Cosign Credentials
        COSIGN_PASSWORD = credentials('cosign-private-key')
        SONAR_SERVER_NAME = "sonar-server-admin"
        SONAR_PROJECT_KEY = "fintech-app-trainer-gg" // Add your name here
    }

    stages {
        stage('Install Dependencies & Test') {
            steps {
                script {
                    echo "--- Setting up Virtual Environment ---"
                    // 1. Create the venv folder
                    sh 'python3 -m venv venv'
                    
                    echo "--- Installing Dependencies (Inside Venv) ---"
                    // 2. Install requirements using the pip INSIDE the venv
                    sh 'venv/bin/pip install --upgrade pip'
                    sh 'venv/bin/pip install -r requirements.txt'
                    
                    echo "--- Running Unit Tests with Coverage ---"
                    // 3. Run pytest using the binary INSIDE the venv
                    sh 'venv/bin/pytest --cov=app --cov-report=xml test_app.py'
                }
            }
        }

        stage('SonarQube Analysis') {
            steps {
                script {
                    echo "--- Starting Static Code Analysis ---"
                    withSonarQubeEnv("${SONAR_SERVER_NAME}") {
                        sh """
                        sonar-scanner \
                          -Dsonar.projectKey=${SONAR_PROJECT_KEY} \
                          -Dsonar.sources=. \
                          -Dsonar.python.coverage.reportPaths=coverage.xml \
                          -Dsonar.exclusions=venv/**,tests/**
                        """
                    }
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "--- Building Docker Image ---"
                    docker.build("${NEXUS_REGISTRY}/${IMAGE_NAME}:${params.VERSION_TAG}")
                }
            }
        }

        stage('Trivy Security Scan') {
            steps {
                script {
                    echo "Scanning Image using Trivy Container..."
                    
                    // --severity: Only show High and Critical bugs
                    // --exit-code 0: Don't fail the build (Change to 1 if you want to block bad builds)
                    // --no-progress: Cleaner logs in Jenkins
                    sh """
                        docker run --rm \
                        -v /var/run/docker.sock:/var/run/docker.sock \
                        aquasec/trivy image \
                        --severity HIGH,CRITICAL \
                        --exit-code 0 \
                        ${NEXUS_REGISTRY}/${IMAGE_NAME}:${params.VERSION_TAG}
                    """
                }
            }
        }

        stage('Generate 1 (Syft)') {
            steps {
                script {
                    echo "--- Generating SBOM ---"
                    sh "syft ${NEXUS_REGISTRY}/${IMAGE_NAME}:${params.VERSION_TAG} -o cyclonedx-json > sbom.json"
                    sh "syft ${NEXUS_REGISTRY}/${IMAGE_NAME}:${params.VERSION_TAG} -o table > sbom.txt"
                }
            }
        }

        stage('Push to Nexus') {
            when { expression { params.ACTION == 'Deploy New Version' } }
            steps {
                script {
                    echo "--- Pushing to Nexus Registry ---"
                    docker.withRegistry("http://${NEXUS_REGISTRY}", "${NEXUS_CRED}") {
                        docker.image("${NEXUS_REGISTRY}/${IMAGE_NAME}:${params.VERSION_TAG}").push()
                    }
                }
            }
        }

        // stage('Sign Image (Cosign)') {
        //     when { expression { params.ACTION == 'Deploy New Version' } }
        //     steps {
        //         withCredentials([
        //             file(credentialsId: 'cosign-private-key', variable: 'COSIGN_KEY_FILE'),
        //             usernamePassword(credentialsId: "${NEXUS_CRED}", usernameVariable: 'NEXUS_USER', passwordVariable: 'NEXUS_PASS')
        //         ]) {
        //             sh '''
        //             #!/bin/bash

        //             echo "--- Debug Info ---"
        //             whoami
        //             which cosign || true
        //             cosign version || true

        //             echo "--- Logging into Nexus ---"
        //             cosign login ${NEXUS_REGISTRY} -u ${NEXUS_USER} -p ${NEXUS_PASS}

        //             echo "--- Signing Image ---"
        //             cosign sign --key ${COSIGN_KEY_FILE} \
        //                 --allow-insecure-registry \
        //                 -y \
        //                 ${NEXUS_REGISTRY}/${IMAGE_NAME}:${VERSION_TAG}
        //             '''
        //         }
        //     }
        // }


        stage('Deploy to Environment') {
            when { expression { params.ACTION == 'Deploy New Version' } }
            steps {
                script {
                    echo "Starting Deployment for Tag: ${params.VERSION_TAG}..."
                    
                    // Cleanup old container
                    sh "docker rm -f ${CONTAINER_NAME} || true"

                    def envColor = params.APP_COLOR
                    def envVersion = params.VERSION_TAG

                    docker.withRegistry("http://${NEXUS_REGISTRY}", "${NEXUS_CRED}") {
                        // Pull logic ensures we use the registry version
                        sh "docker pull ${NEXUS_REGISTRY}/${IMAGE_NAME}:${params.VERSION_TAG}"
                        
                        sh """
                            docker run -d \
                            --name ${CONTAINER_NAME} \
                            -p ${ZAP_PORT}:8080 \
                            -e APP_VERSION="${envVersion}" \
                            -e BG_COLOR="${envColor}" \
                            ${NEXUS_REGISTRY}/${IMAGE_NAME}:${params.VERSION_TAG}
                        """
                    }
                    
                    // Wait for app to boot before ZAP scans it
                    sh "sleep 5"
                }
            }
        }

        stage('DAST Scan (OWASP ZAP)') {
            when { expression { params.ACTION == 'Deploy New Version' } }
            steps {
                script {
                    echo "--- Running OWASP ZAP Scan ---"
                    def hostIP = "host.docker.internal"                    
                    try {
                        // 1. Create directory and ensure ANY user (including Docker's zap user) can write to it
                        sh "mkdir -p $WORKSPACE/zap-wrk && chmod 777 $WORKSPACE/zap-wrk"

                        sh """
                        docker run --rm \
                        -v $WORKSPACE/zap-wrk:/zap/wrk:rw \
                        --network host \
                        zaproxy/zap-stable \
                        zap-baseline.py \
                        -t http://localhost:${ZAP_PORT} \
                        -r /zap/wrk/zap_report.html \
                        -g /zap/wrk/zap.yaml \
                        || true 
                        """
                    } catch (Exception e) {
                        echo "ZAP Warning: ${e.getMessage()}"
                    }
                }
            }
        }
    }

    post {
        always {
            // Publish ZAP HTML Report
            publishHTML (target : [
                allowMissing: true,
                alwaysLinkToLastBuild: true,
                keepAll: true,
                reportDir: 'zap-wrk',          // <--- CHANGED: Look inside the sub-folder
                reportFiles: 'zap_report.html',
                reportName: 'OWASP ZAP Report'
            ])
            
            // Archive SBOM
            archiveArtifacts artifacts: 'sbom.json', fingerprint: true
            archiveArtifacts artifacts: 'sbom.txt', fingerprint: true
            archiveArtifacts artifacts: 'zap-wrk/zap_report.html', fingerprint: true

            
            // Cleanup
            cleanWs()
        }
    }
}