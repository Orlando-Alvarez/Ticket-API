import importlib.util
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ZONE_ID = "a" * 32
RECORD_ID = "b" * 32
PUBLIC_IP = "198.51.100.20"
OLD_IP = "198.51.100.10"


@pytest.fixture
def ddns():
    path = (
        Path(__file__).resolve().parents[1]
        / "ansible"
        / "files"
        / "cloudflare_ddns.py"
    )

    spec = importlib.util.spec_from_file_location(
        "ticket_api_cloudflare_ddns",
        path,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def prepare_sync(monkeypatch, ddns, public_ip, dns_ip, apply=False):
    args = ["cloudflare_ddns.py", "--zone-id", ZONE_ID]

    if apply:
        args.append("--apply")

    monkeypatch.setattr(sys, "argv", args)
    monkeypatch.setattr(ddns, "get_public_ip", lambda: public_ip)
    monkeypatch.setattr(
        ddns, "get_cloudflare_token", lambda: "fake-test-token"
    )
    monkeypatch.setattr(
        ddns,
        "get_dns_record",
        lambda zone_id, token: {
            "id": RECORD_ID,
            "type": "A",
            "name": ddns.RECORD_NAME,
            "content": dns_ip,
            "proxied": False,
        },
    )

    request_mock = Mock(return_value={"content": public_ip})
    monkeypatch.setattr(ddns, "cloudflare_request", request_mock)

    return request_mock


def test_unchanged_dns_does_not_update(monkeypatch, ddns, capsys):
    request = prepare_sync(
        monkeypatch, ddns, PUBLIC_IP, PUBLIC_IP, apply=True
    )

    ddns.main()

    request.assert_not_called()
    assert "UNCHANGED" in capsys.readouterr().out


def test_dry_run_never_updates_dns(monkeypatch, ddns, capsys):
    request = prepare_sync(
        monkeypatch, ddns, PUBLIC_IP, OLD_IP
    )

    ddns.main()

    request.assert_not_called()
    assert "DRY-RUN" in capsys.readouterr().out


def test_apply_updates_changed_ip(monkeypatch, ddns, capsys):
    request = prepare_sync(
        monkeypatch, ddns, PUBLIC_IP, OLD_IP, apply=True
    )

    ddns.main()

    request.assert_called_once_with(
        "PATCH",
        ZONE_ID,
        "fake-test-token",
        f"/{RECORD_ID}",
        {"content": PUBLIC_IP},
    )

    assert "UPDATED" in capsys.readouterr().out


def test_invalid_zone_id_is_rejected(monkeypatch, ddns):
    monkeypatch.setattr(
        sys,
        "argv",
        ["cloudflare_ddns.py", "--zone-id", "invalid"],
    )

    with pytest.raises(SystemExit) as error:
        ddns.main()

    assert error.value.code == 2


@pytest.mark.parametrize("records", [[], [{}, {}]])
def test_missing_or_duplicate_records_are_rejected(
    monkeypatch, ddns, records
):
    monkeypatch.setattr(
        ddns,
        "cloudflare_request",
        lambda *args: records,
    )

    with pytest.raises(RuntimeError, match="exactly one"):
        ddns.get_dns_record(ZONE_ID, "fake-test-token")


def test_proxied_record_is_rejected(monkeypatch, ddns):
    record = {
        "id": RECORD_ID,
        "type": "A",
        "name": ddns.RECORD_NAME,
        "content": OLD_IP,
        "proxied": True,
    }

    monkeypatch.setattr(
        ddns,
        "cloudflare_request",
        lambda *args: [record],
    )

    with pytest.raises(RuntimeError, match="DNS only"):
        ddns.get_dns_record(ZONE_ID, "fake-test-token")
