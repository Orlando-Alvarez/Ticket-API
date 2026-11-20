import os
import tempfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


REGION = "us-west-2"
PARAMETER_NAME = "/ticket-api/dev/cloudflare-certbot-token"
CREDENTIALS_PATH = Path(
    "/etc/ticket-api/cloudflare-certbot.ini"
)


def get_token() -> str:
    """Retrieve the Cloudflare token through the EC2 IAM role."""
    client = boto3.client("ssm", region_name=REGION)

    try:
        response = client.get_parameter(
            Name=PARAMETER_NAME,
            WithDecryption=True,
        )
    except ClientError as error:
        code = error.response["Error"]["Code"]
        raise RuntimeError(f"SSM request failed: {code}") from None

    parameter = response["Parameter"]

    if parameter["Type"] != "SecureString":
        raise RuntimeError("Expected a SecureString parameter")

    token = parameter["Value"]

    if not token or "\n" in token or "\r" in token:
        raise RuntimeError("Invalid Cloudflare token value")

    return token


def synchronize_credentials() -> None:
    """Atomically update the root-only Certbot credentials file."""
    token = get_token()

    directory = CREDENTIALS_PATH.parent
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)

    content = (
        f"dns_cloudflare_api_token = {token}\n"
    ).encode("utf-8")

    if CREDENTIALS_PATH.exists():
        if CREDENTIALS_PATH.read_bytes() == content:
            CREDENTIALS_PATH.chmod(0o600)
            print("UNCHANGED: Certbot credentials synchronized")
            return

    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".certbot-",
        dir=directory,
    )

    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)

        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, CREDENTIALS_PATH)
        CREDENTIALS_PATH.chmod(0o600)

    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)

    print("UPDATED: Certbot credentials synchronized")


if __name__ == "__main__":
    synchronize_credentials()
