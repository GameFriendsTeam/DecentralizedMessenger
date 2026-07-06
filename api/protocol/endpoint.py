"""
CTP (Custom Transport Protocol) Endpoint — asyncio UDP socket wrapper.

Usage:

    # Server side
    endpoint = await Endpoint.create(host="0.0.0.0", port=9000)
    conn = await endpoint.accept()           # wait for first packet from new peer
    stream = conn.get_stream(1)
    data = await stream.recv()

    # Client side
    endpoint = await Endpoint.create(host="0.0.0.0", port=0)
    conn = endpoint.connect(("server.ip", 9000))
    stream = conn.open_stream(1, reliable=True, ordered=True)
    await stream.send(b"hello")
"""

import asyncio
import logging
from typing import Callable

from .connection import Connection
from .packet import Packet

log = logging.getLogger("ctp.endpoint")


class _CTPProtocol(asyncio.DatagramProtocol):
    """asyncio protocol glue — receives datagrams and dispatches to connections."""

    def __init__(self, on_packet: Callable, on_error: Callable) -> None:
        self._on_packet = on_packet
        self._on_error  = on_error
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            pkt = Packet.decode(data)
            self._on_packet(pkt, addr)
        except Exception as exc:
            log.debug("Bad packet from %s: %s", addr, exc)

    def error_received(self, exc: Exception) -> None:
        self._on_error(exc)

    def connection_lost(self, exc: Exception | None) -> None:
        pass


class Endpoint:
    """
    A UDP endpoint that manages multiple CTP Connections.

    One Endpoint = one UDP socket (one port).
    Can hold connections to many remotes simultaneously.
    """

    def __init__(self) -> None:
        self._connections: dict[tuple, Connection] = {}
        self._transport:   asyncio.DatagramTransport | None = None
        self._new_conn_queue: asyncio.Queue | None = None

    # ==================================================================== create

    @classmethod
    async def create(cls, host: str = "0.0.0.0", port: int = 0) -> "Endpoint":
        """Bind the endpoint to host:port. port=0 picks a free port (client mode)."""
        ep = cls()
        # Queue must be created inside running loop so it binds to the correct one
        ep._new_conn_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _CTPProtocol(ep._on_packet, ep._on_error),
            local_addr=(host, port),
        )
        ep._transport = transport
        sock = transport.get_extra_info("socket")
        actual_addr = sock.getsockname()
        log.info("CTP Endpoint bound to %s", actual_addr)
        return ep

    # ====================================================================== API

    def connect(self, remote_addr: tuple) -> Connection:
        """
        Open a Connection to a remote address.
        Does NOT send anything yet — streams send the first packets.
        """
        addr = (remote_addr[0], remote_addr[1])
        if addr in self._connections:
            return self._connections[addr]
        conn = Connection(remote_addr=addr, transport=self._transport)
        conn.start()
        self._connections[addr] = conn
        log.info("Connected to %s", addr)
        return conn

    async def accept(self) -> Connection:
        """
        Wait until a packet arrives from an unknown remote.
        Returns the auto-created Connection for that remote.
        """
        return await self._new_conn_queue.get()

    async def close(self) -> None:
        for conn in self._connections.values():
            await conn.close()
        if self._transport:
            self._transport.close()

    @property
    def local_addr(self) -> tuple:
        sock = self._transport.get_extra_info("socket")
        return sock.getsockname()

    # ================================================================= internal

    def _on_packet(self, pkt: Packet, addr: tuple) -> None:
        addr = (addr[0], addr[1])

        if addr not in self._connections:
            # New remote — auto-create connection
            conn = Connection(remote_addr=addr, transport=self._transport)
            conn.start()
            self._connections[addr] = conn
            log.info("New connection from %s", addr)
            self._new_conn_queue.put_nowait(conn)

        self._connections[addr].packet_received(pkt)

    def _on_error(self, exc: Exception) -> None:
        log.warning("UDP error: %s", exc)

    def __repr__(self) -> str:
        return f"Endpoint(conns={len(self._connections)}, addr={self.local_addr})"
