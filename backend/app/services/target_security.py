"""Outbound target validation to constrain test execution."""

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit, urlunsplit

import httpcore
import httpx

from app.config import TEST_ALLOWED_TARGET_HOSTS, TEST_ALLOWED_TARGET_PORTS, TEST_ALLOW_PRIVATE_TARGETS

BLOCKED_METADATA_HOSTS = {"metadata", "metadata.google.internal", "instance-data"}
BLOCKED_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("169.254.170.2"),
    ipaddress.ip_address("168.63.129.16"),
    ipaddress.ip_address("100.100.100.200"),
}


class TargetValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedTarget:
    url: str
    hostname: str
    port: int
    addresses: tuple[str, ...]


def resolve_target_url(base_url: str) -> ValidatedTarget:
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise TargetValidationError("Target URL must use http:// or https:// and include a hostname.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise TargetValidationError("Target URL must not contain credentials, query parameters, or a fragment.")
    if "\\" in parsed.path or any(part in {".", ".."} for part in unquote(parsed.path).split("/")):
        raise TargetValidationError("Target base URL contains an invalid path prefix.")

    host = parsed.hostname.lower().rstrip(".")
    if host in BLOCKED_METADATA_HOSTS:
        raise TargetValidationError("Cloud metadata hostnames are prohibited.")
    if host not in TEST_ALLOWED_TARGET_HOSTS:
        raise TargetValidationError("Target host is not allowlisted. Add its exact hostname to CONTRACTIQ_TEST_ALLOWED_TARGET_HOSTS.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise TargetValidationError("Target URL contains an invalid port.") from exc
    if port not in TEST_ALLOWED_TARGET_PORTS:
        raise TargetValidationError("Target port is not allowlisted. Add it to CONTRACTIQ_TEST_ALLOWED_TARGET_PORTS.")
    try:
        addresses = {ipaddress.ip_address(host)} if _is_ip(host) else {
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError) as exc:
        raise TargetValidationError("Target hostname could not be resolved.") from exc
    if not addresses:
        raise TargetValidationError("Target hostname resolved to no addresses.")
    for address in addresses:
        if address in BLOCKED_METADATA_IPS:
            raise TargetValidationError("Cloud metadata addresses are prohibited.")
        if address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified:
            raise TargetValidationError("Target resolves to a prohibited network address.")
        if not TEST_ALLOW_PRIVATE_TARGETS and not address.is_global:
            raise TargetValidationError("Private and localhost targets are disabled; enable only for explicit development targets.")
    return ValidatedTarget(
        url=urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")),
        hostname=host,
        port=port,
        addresses=tuple(sorted(address.compressed for address in addresses)),
    )


def validate_target_url(base_url: str) -> str:
    return resolve_target_url(base_url).url


class _PinnedSyncBackend(httpcore.SyncBackend):
    def __init__(self, target: ValidatedTarget):
        self._hostname = target.hostname
        self._port = target.port
        self._addresses = target.addresses

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host.lower().rstrip(".") != self._hostname or port != self._port:
            raise httpcore.ConnectError("HTTPX attempted to connect outside the validated target.")
        last_error = None
        for address in self._addresses:
            try:
                return super().connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except httpcore.ConnectTimeout:
                raise
            except httpcore.ConnectError as exc:
                last_error = exc
        if last_error is None:
            raise httpcore.ConnectError("Validated target has no usable network addresses.")
        raise last_error


class PinnedHTTPTransport(httpx.HTTPTransport):
    def __init__(self, target: ValidatedTarget, *, limits: httpx.Limits):
        super().__init__(trust_env=False, limits=limits)
        # HTTPX does not expose a public network-backend argument on HTTPTransport.
        self._pool._network_backend = _PinnedSyncBackend(target)


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False
