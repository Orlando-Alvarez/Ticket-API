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
                        env.VERIFIED_RELEASE_SHA = selectedSha

                        echo "Selected tag: sha-${selectedSha}"
                        echo "Validated image digest: ${digest}"
                    }
                }
            }
        }

        stage('Verify Release Commit') {
            steps {
                sh '''
                    set -eu

                    echo "Verifying release commit against main..."

                    git fetch --no-tags origin \
                        '+refs/heads/main:refs/remotes/origin/main'

                    git cat-file -e "${VERIFIED_RELEASE_SHA}^{commit}"

                    if ! git merge-base --is-ancestor \
                        "$VERIFIED_RELEASE_SHA" \
                        "refs/remotes/origin/main"; then

                        echo "ERROR: Release commit is not in main" >&2
                        exit 1
                    fi

                    echo "Release commit verified in main"
                '''
            }
        }
        stage('Verify Deployment Tooling'){
            steps{
                sh '''
                    set -eu

                    echo "Checking AWS CLI..."
                    aws --version

                    echo "Checking Ansible..."
                    /opt/ansible/bin/ansible --version

                    echo "Checking Session Manager Plugin..."
                    session-manager-plugin --version

                    echo "Checking AWS identity..."
                    aws sts get-caller-identity \
                        --query Arn \
                        --output text

                    echo "Deployment tooling verification completed"
                '''
            }
        }
        stage('Verify Ansible Inventory') {
            steps {
                sh '''
                    set -eu
        
                    echo "Checking Ansible inventory..."
        
                    /opt/ansible/bin/ansible-inventory \
                        -i ansible/Inventory/hosts.yml \
                        --host ticket-api-ec2
        
                    echo "Checking resolved AWS profile..."
        
                    /opt/ansible/bin/ansible \
                        -i ansible/Inventory/hosts.yml \
                        ticket-api-ec2 \
                        -c local \
                        -m ansible.builtin.debug \
                        -a 'var=ansible_aws_ssm_profile'
        
                    echo "Inventory validation completed"
                '''
            }
        }
        stage('Validate Deployment Playbook') {
            steps {
                sh '''
                    set -eu

                    echo "Validating deployment playbook..."

                    test -n "$RELEASE_DIGEST"

                    /opt/ansible/bin/ansible-playbook \
                        -i ansible/Inventory/hosts.yml \
                        ansible/playbooks/deploy_app.yml \
                        --syntax-check \
                        -e "image_digest=$RELEASE_DIGEST"

                    echo "Deployment playbook validation successful"
                '''
            }
        }
        stage('Approve Deployment') {
            steps {
                script {
                    def approvedBy = timeout(time: 5, unit: 'MINUTES') {
                        return input(
                            message: """Approve deployment of Ticket-API?

        Commit: ${params.RELEASE_SHA}
        Image digest: ${env.RELEASE_DIGEST}

        DRY RUN: No EC2 deployment will occur.""",
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
        stage('Verify SSM Connectivity') {
            steps {
                timeout(time: 3, unit: 'MINUTES') {
                    sh '''
                        set -eu

                        echo "Testing Jenkins to EC2 connectivity..."

                        /opt/ansible/bin/ansible \
                            -i ansible/Inventory/hosts.yml \
                            ticket-api-ec2 \
                            -m ansible.builtin.command \
                            -a 'hostname'

                        echo "SSM connectivity verified successfully"
                    '''
                }
            }
        }
        stage('Verify EC2 Deployment Prerequisites') {
            steps {
                timeout(time: 3, unit: 'MINUTES') {
                    sh '''
                        set -eu

                        echo "Checking EC2 deployment prerequisites..."

                        /opt/ansible/bin/ansible-playbook \
                            -i ansible/Inventory/hosts.yml \
                            ansible/playbooks/preflight.yml

                        echo "EC2 deployment prerequisites verified"
                    '''
                }
                archiveArtifacts(
                    artifacts: 'previous-image.txt',
                    fingerprint: true
                )
            }
        }
        stage('Verify Rollback Image') {
            steps {
                sh '''
                    set -eu

                    echo "Checking previous image availability..."

                    test -s previous-image.txt

                    PREVIOUS_IMAGE="$(cat previous-image.txt)"
                    PREVIOUS_DIGEST="${PREVIOUS_IMAGE##*@}"

                    if ! printf '%s\\n' "$PREVIOUS_DIGEST" |
                        grep -Eq '^sha256:[0-9a-f]{64}$'; then
                        echo "Invalid previous image digest" >&2
                        exit 1
                    fi

                    EXPECTED_REGISTRY="891920435362.dkr.ecr.us-west-2.amazonaws.com/ticket-api"

                    if [ "$PREVIOUS_IMAGE" != "$EXPECTED_REGISTRY@$PREVIOUS_DIGEST" ]; then
                        echo "Unexpected previous image repository" >&2
                        exit 1
                    fi

                    aws ecr describe-images \
                        --repository-name "$ECR_REPOSITORY" \
                        --image-ids "imageDigest=$PREVIOUS_DIGEST" \
                        --query 'imageDetails[0].imageDigest' \
                        --output text

                    echo "Previous release is available in ECR"
                '''
            }
        }

    }
}
