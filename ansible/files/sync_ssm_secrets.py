
import os
import re
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ENV_PATH = Path("/opt/ticket-api/.env")
REGION = "us-west-2"

PARAMETERS = {
    "POSTGRES_PASSWORD": "/ticket-api/dev/postgres-password",
    "JWT_SECRET_KEY": "/ticket-api/dev/jwt-secret",
}

DEFAULTS = {
    "POSTGRES_USER": "ticket_user",
    "POSTGRES_DB": "ticket_api",
    "APP_DEBUG": "false",
}


def read_existing_env(path: Path) -> dict[str, str]:
    values = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#"):
            continue

        key, separator, value = line.partition("=")

        if separator:
            if key in values:
                raise RuntimeError(f"Duplicate environment key: {key}")
            values[key] = value

    return values


def main():
    ssm = boto3.client("ssm", region_name=REGION)
    secrets = {}

    for key, parameter_name in PARAMETERS.items():
        response = ssm.get_parameter(
            Name=parameter_name,
            WithDecryption=True,
        )

        parameter = response["Parameter"]
        value = parameter["Value"]

        if parameter["Type"] != "SecureString":
            raise RuntimeError(f"Parameter is not SecureString: {parameter_name}")

        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise RuntimeError(f"Unexpected secret format: {parameter_name}")

        secrets[key] = value

    if ENV_PATH.is_symlink():
        raise RuntimeError("Environment path must not be a symlink")

    if ENV_PATH.exists():
        if not ENV_PATH.is_file():
            raise RuntimeError("Environment path is not a regular file")

        current = read_existing_env(ENV_PATH)

        for key, expected in secrets.items():
            if current.get(key) != expected:
                raise RuntimeError(
                    f"Secret mismatch for {key}; refusing to change .env"
                )

        for key in ("POSTGRES_USER", "POSTGRES_DB"):
            if current.get(key) != DEFAULTS[key]:
                raise RuntimeError(f"Unexpected database setting: {key}")

        print("VERIFIED: Existing environment matches Parameter Store")
        return

    values = {**DEFAULTS, **secrets}
    content = "".join(f"{key}={value}\n" for key, value in values.items())

    fd = os.open(
        ENV_PATH,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )

    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(content)

    print("CREATED: Environment restored from Parameter Store")


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        code = error.response["Error"]["Code"]
        raise SystemExit(f"AWS operation failed: {code}")
    except (RuntimeError, OSError) as error:
        raise SystemExit(f"Secret synchronization failed: {error}")
