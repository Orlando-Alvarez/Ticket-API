
import argparse
import ipaddress
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener, urlopen

import boto3
from botocore.exceptions import ClientError

REGION = "us-west-2"
RECORD_NAME = "api.orlandoalvarez.dev"
SSM_PARAMETER = "/ticket-api/dev/cloudflare-ddns-token"
IMDS_URL = "http://169.254.169.254/latest"


def get_public_ip():
    """Read EC2 public IPv4 using IMDSv2."""
    direct = build_opener(ProxyHandler({}))

    token_request = Request(
        f"{IMDS_URL}/api/token",
        method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
    )

    with direct.open(token_request, timeout=3) as response:
        metadata_token = response.read().decode("utf-8")

    ip_request = Request(
        f"{IMDS_URL}/meta-data/public-ipv4",
        headers={"X-aws-ec2-metadata-token": metadata_token},
    )

    with direct.open(ip_request, timeout=3) as response:
        raw_ip = response.read().decode("utf-8").strip()

    address = ipaddress.IPv4Address(raw_ip)

    if not address.is_global:
        raise RuntimeError("EC2 did not return a public IPv4 address")

    return str(address)


def get_cloudflare_token():
    """Retrieve the encrypted API token using the EC2 IAM role."""
    ssm = boto3.client("ssm", region_name=REGION)

    try:
        response = ssm.get_parameter(
            Name=SSM_PARAMETER,
            WithDecryption=True,
        )
    except ClientError as error:
        code = error.response["Error"]["Code"]
        raise RuntimeError(f"SSM request failed: {code}") from None

    parameter = response["Parameter"]

    if parameter["Type"] != "SecureString":
        raise RuntimeError("Cloudflare token must be SecureString")

    token = parameter["Value"]

    if not token:
        raise RuntimeError("Cloudflare token is empty")

    return token


def cloudflare_request(method, zone_id, token, suffix, payload=None):
    """Send an authenticated request to Cloudflare DNS API."""
    url = (
        "https://api.cloudflare.com/client/v4/zones/"
        f"{zone_id}/dns_records{suffix}"
    )

    data = json.dumps(payload).encode("utf-8") if payload else None

    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
    except HTTPError as error:
        raise RuntimeError(
            f"Cloudflare returned HTTP {error.code}"
        ) from None
    except (URLError, TimeoutError):
        raise RuntimeError("Could not connect to Cloudflare") from None

    if result.get("success") is not True:
        raise RuntimeError("Cloudflare API reported a failure")

    return result["result"]


def get_dns_record(zone_id, token):
    """Find exactly one existing, non-proxied A record."""
    query = urlencode({
        "type": "A",
        "name": RECORD_NAME,
        "per_page": 100,
    })

    records = cloudflare_request(
        "GET", zone_id, token, f"?{query}"
    )

    if len(records) != 1:
        raise RuntimeError("Expected exactly one Cloudflare A record")

    record = records[0]

    if record["name"] != RECORD_NAME or record["type"] != "A":
        raise RuntimeError("Unexpected Cloudflare DNS record")

    if record.get("proxied") is not False:
        raise RuntimeError("DNS record must use DNS only")

    if not re.fullmatch(r"[0-9a-fA-F]{32}", record["id"]):
        raise RuntimeError("Invalid DNS record identifier")

    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zone-id", required=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually update Cloudflare (default: dry-run)",
    )
    args = parser.parse_args()

    if not re.fullmatch(r"[0-9a-fA-F]{32}", args.zone_id):
        parser.error("Zone ID must be 32 hexadecimal characters")

    public_ip = get_public_ip()
    cloudflare_token = get_cloudflare_token()
    record = get_dns_record(args.zone_id, cloudflare_token)

    previous_ip = record["content"]

    if previous_ip == public_ip:
        print("UNCHANGED: DNS already matches EC2 public IPv4")
        return

    if not args.apply:
        print(
            f"DRY-RUN: Would update {RECORD_NAME} "
            f"from {previous_ip} to {public_ip}"
        )
        return

    updated = cloudflare_request(
        "PATCH",
        args.zone_id,
        cloudflare_token,
        f"/{record['id']}",
        {"content": public_ip},
    )

    if updated["content"] != public_ip:
        raise RuntimeError("Cloudflare update verification failed")

    print(f"UPDATED: {RECORD_NAME} now points to {public_ip}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        raise SystemExit(f"DNS synchronization failed: {error}")
