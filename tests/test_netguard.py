import socket
import urllib.request

import pytest

from jarvis import netguard


def resolve(monkeypatch, *addresses):
    def fake(host, port, **kwargs):
        family = socket.AF_INET6 if ":" in addresses[0] else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 6, "", (a, port)) for a in addresses]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "fe80::1%12",
    ],
)
def test_private_addresses_are_blocked(monkeypatch, address):
    resolve(monkeypatch, address)

    with pytest.raises(netguard.BlockedAddress, match="private network"):
        netguard.check_public("http://anything.example/")


def test_one_private_answer_among_public_ones_blocks(monkeypatch):
    resolve(monkeypatch, "93.184.215.14", "10.0.0.1")

    with pytest.raises(netguard.BlockedAddress):
        netguard.check_public("https://mixed.example/")


def test_a_public_address_is_allowed(monkeypatch):
    resolve(monkeypatch, "93.184.215.14")

    netguard.check_public("https://example.com/page")


def test_an_unresolvable_name_is_not_a_block(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", fail)

    netguard.check_public("https://no-such-host.example/")


def test_the_port_comes_from_the_url_or_the_scheme(monkeypatch):
    ports = []

    def fake(host, port, **kwargs):
        ports.append(port)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    for url in ("http://a.example/", "https://a.example/", "http://a.example:8080/"):
        netguard.check_public(url)

    assert ports == [80, 443, 8080]


def redirect(url):
    request = urllib.request.Request("http://start.example/")
    return netguard.GuardedRedirectHandler().redirect_request(
        request, None, 302, "Found", {}, url
    )


def test_a_redirect_to_a_private_address_is_refused(monkeypatch):
    resolve(monkeypatch, "192.168.1.1")

    with pytest.raises(netguard.BlockedAddress):
        redirect("http://router.example/admin")


def test_a_redirect_to_a_public_address_is_followed(monkeypatch):
    resolve(monkeypatch, "93.184.215.14")

    assert redirect("http://next.example/").full_url == "http://next.example/"
