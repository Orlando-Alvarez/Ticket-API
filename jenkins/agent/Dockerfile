FROM jenkins/inbound-agent:jdk21

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        unzip \
        git \
        python3 \
        python3-venv && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/ansible && \
    /opt/ansible/bin/pip install --no-cache-dir \
        "ansible-core>=2.18,<2.20" \
        "boto3>=1.34,<2" \
        "botocore[crt]>=1.34,<2"

ENV PATH="/opt/ansible/bin:${PATH}"

RUN ansible-galaxy collection install \
    amazon.aws \
    community.docker \
    -p /usr/share/ansible/collections

RUN curl -fsSL \
    "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
    -o /tmp/awscliv2.zip && \
    unzip -q /tmp/awscliv2.zip -d /tmp && \
    /tmp/aws/install && \
    rm -rf /tmp/aws /tmp/awscliv2.zip

RUN curl -fsSL \
    "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" \
    -o /tmp/session-manager-plugin.deb && \
    dpkg -i /tmp/session-manager-plugin.deb && \
    rm -f /tmp/session-manager-plugin.deb

USER jenkins
