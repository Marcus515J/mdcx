"""Local TLS/CONNECT checks: no external site, user proxy, or stored credentials."""

import asyncio
import contextlib
import itertools
import shutil
import ssl
import subprocess

import pytest
from curl_cffi import CurlOpt

import mdcx.web_async as web_async
from mdcx.network_fingerprint import _DEFAULT_FINGERPRINTS


@pytest.mark.asyncio
@pytest.mark.parametrize("use_proxy", [False, True], ids=["direct-tls", "connect-proxy-tls"])
async def test_all_profiles_with_concurrent_tls_and_pool_rotation(tmp_path, monkeypatch, use_proxy):
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("Local TLS fixture needs openssl to generate an ephemeral certificate")
    key = tmp_path / "test-only-key.pem"
    cert = tmp_path / "test-only-cert.pem"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_context.load_cert_chain(cert, key)
    tls_context.set_alpn_protocols(["http/1.1"])
    tasks = set()
    http_requests = []
    tunnels = []

    async def endpoint(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        try:
            raw = await reader.readuntil(b"\r\n\r\n")
            http_requests.append(raw.split(b"\r\n", 1)[0])
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            await writer.drain()
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
            tasks.discard(task)

    tls_server = await asyncio.start_server(endpoint, "127.0.0.1", 0, ssl=tls_context)
    tls_port = tls_server.sockets[0].getsockname()[1]

    async def proxy(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        upstream = None
        relays = []
        try:
            raw = await reader.readuntil(b"\r\n\r\n")
            target = raw.split(b"\r\n", 1)[0]
            assert target.startswith(b"CONNECT ")
            tunnels.append(target)
            upstream_reader, upstream = await asyncio.open_connection("127.0.0.1", tls_port)
            writer.write(b"HTTP/1.1 200 Connection established\r\n\r\n")
            await writer.drain()

            async def relay(source, destination):
                while chunk := await source.read(65536):
                    destination.write(chunk)
                    await destination.drain()

            relays = [asyncio.create_task(relay(reader, upstream)), asyncio.create_task(relay(upstream_reader, writer))]
            await asyncio.wait(relays, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for relay_task in relays:
                relay_task.cancel()
            await asyncio.gather(*relays, return_exceptions=True)
            for stream in [writer, upstream]:
                if stream is not None:
                    stream.close()
                    with contextlib.suppress(Exception):
                        await stream.wait_closed()
            tasks.discard(task)

    proxy_server = await asyncio.start_server(proxy, "127.0.0.1", 0)
    proxy_port = proxy_server.sockets[0].getsockname()[1]
    profiles = itertools.cycle(_DEFAULT_FINGERPRINTS)
    used = []

    def select_profile(*args, **kwargs):
        profile = next(profiles)
        used.append(profile.fingerprint_id)
        return profile

    monkeypatch.setattr(web_async, "select_fingerprint", select_profile)
    client = web_async.AsyncWebClient(timeout=3, retry=1, proxy=f"http://127.0.0.1:{proxy_port}" if use_proxy else "")
    client._fingerprint_default_request_range = (1, 1)
    hosts = ["tls-a.test", "tls-b.test"]
    client._session_kwargs["curl_options"] = {CurlOpt.RESOLVE: [f"{host}:{tls_port}:127.0.0.1" for host in hosts]}
    if not use_proxy:
        client._session_kwargs["curl_options"][CurlOpt.PROXY] = ""
    try:
        for wave in range(8):
            results = await asyncio.gather(
                *[client.get_text(f"https://{hosts[index % 2]}:{tls_port}/probe-{wave}-{index}") for index in range(3)]
            )
            assert results == [("ok", "")] * 3
            await client.reset_connections("local TLS regression rotation")
        assert len(http_requests) == 24
        assert set(used) == {profile.fingerprint_id for profile in _DEFAULT_FINGERPRINTS}
        assert bool(tunnels) == use_proxy
    finally:
        await client.close()
        for server in [tls_server, proxy_server]:
            server.close()
            await server.wait_closed()
        for task in list(tasks):
            task.cancel()
        await asyncio.gather(*list(tasks), return_exceptions=True)
