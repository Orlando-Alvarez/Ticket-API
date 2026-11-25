pipeline{
    agent{
        label 'ticket-api-cd'
    }

    options{
        disableConcurrentBuilds()
        timeout(time:10, unit: 'MINUTES')
    }

    parameters{
        string(
            name: 'RELEASE_SHA',
            defaultValue: '',
            description: 'Full 40-character Git commit SHA published to ECR'
        )
    }

    environment{
        AWS_PROFILE = 'ticketapi-jenkins'
        AWS_DEFAULT_REGION = 'us-west-2'
        ECR_REPOSITORY = 'ticket-api'
    }

    stages{
        stage('Verify AWS Identity'){
            steps{
                sh '''
                    set -eu

                    ACTUAL_ARN="$(aws sts get-caller-identity \
                        --query Arn --output text)"

                        echo "$ACTUAL_ARN"

                    case "$ACTUAL_ARN" in
                        arn:aws:sts::891920435362:assumed-role/ticket-api-dev-jenkins-deployer/*)
                            echo "Correct Jenkins IAM role"
                            ;;
                        *)
                            echo "Unexpected AWS identity" >&2
                            exit 1
                            ;;
                        esac
                '''
            }
        }
        stage('Resolve Release Image') {
            steps {
                script {
                    def selectedSha = params.RELEASE_SHA?.trim()

                    echo "SHA length: ${selectedSha?.length()}"

                    if (!(selectedSha ==~ /^[0-9a-f]{40}$/)) {
                        error('RELEASE_SHA must contain 40 lowercase hexadecimal characters')
                    }

                    withEnv(["RELEASE_SHA=${selectedSha}"]) {
                        def digest = sh(
                            script: '''
                                set -eu

                                aws ecr describe-images \
                                    --repository-name "$ECR_REPOSITORY" \
                                    --image-ids "imageTag=sha-${RELEASE_SHA}" \
                                    --query 'imageDetails[0].imageDigest' \
                                    --output text
                            ''',
                            returnStdout: true
                        ).trim()

                        if (!(digest ==~ /^sha256:[0-9a-f]{64}$/)) {
                            error('ECR returned an invalid image digest')
                        }

                        env.RELEASE_DIGEST = digest

                        echo "Selected tag: sha-${selectedSha}"
                        echo "Validated image digest: ${digest}"
                    }
                }
            }
        }
        stage('Approve Deployment') {
            steps {
                script {
                    timeout(time: 5, unit: 'MINUTES') {
                        input(
                            message: """Approve deployment of Ticket-API?

        Commit: ${params.RELEASE_SHA}
        Image digest: ${env.RELEASE_DIGEST}

        This is a test. No EC2 deployment will occur.""",
                            ok: 'Approve',
                            submitter: 'Admin',
                            submitterParameter: 'APPROVED_BY'
                        )
                    }

                    echo "Deployment approved by: ${approvedBy}"
                    echo "Release digest: ${env.RELEASE_DIGEST}"
                    echo 'DRY RUN: No changes were made to EC2'
                }
            }
        }
    }
}
