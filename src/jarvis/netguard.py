"""Refuse web addresses that lead to this PC or its private network, so a page or a
mistaken request cannot make Jarvis read local services. Standard library only."""

import ipaddress
import socket
import urllib.parse
import urllib.request


class BlockedAddress(ValueError):
    pass


def check_public(url: str) -> None:
    """Raise BlockedAddress unless every address the host resolves to is public."""
    parts = urllib.parse.urlparse(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        # the resolver's answer is what gets connected to, so odd spellings such as
        # 127.1, 0x7f.1 and 2130706433 are covered with no special code
        found = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return  # the fetch itself then fails with the usual "could not read"
    for info in found:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        address = getattr(address, "ipv4_mapped", None) or address
        if not address.is_global:
            raise BlockedAddress("blocked: that address is on a private network")


class GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)
