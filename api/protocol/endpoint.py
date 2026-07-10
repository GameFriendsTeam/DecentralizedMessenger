"""
MTP Endpoint — asyncio UDP socket wrapper.
"""

import asyncio
import logging
import socket
import sys
from typing import Callable

from .connection import Connection
from .packet import Packet

log = logging.getLogger("mtp.endpoint")


class _MTPProtocol(asyncio.DatagramProtocol):
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
    def __init__(self) -> None:
        self._connections: dict[tuple, Connection] = {}
        self._transport:   asyncio.DatagramTransport | None = None
        self._new_conn_queue: asyncio.Queue | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    async def create(cls, host: str = "0.0.0.0", port: int = 0) -> "Endpoint":
        ep = cls()
        ep._loop = asyncio.get_running_loop()
        ep._new_conn_queue = asyncio.Queue()  # создаётся внутри running loop

        raw_sock = cls._make_socket(host, port)
        transport, _ = await ep._loop.create_datagram_endpoint(
            lambda: _MTPProtocol(ep._on_packet, ep._on_error),
            sock=raw_sock,
        )
        ep._transport = transport
        sock = transport.get_extra_info("socket")
        log.info("MTP Endpoint bound to %s", sock.getsockname())
        return ep

    @staticmethod
    def _disable_udp_connreset(sock: socket.socket) -> None:
        """
        Отключает SIO_UDP_CONNRESET через прямой вызов WSAIoctl (ctypes).

        socket.socket.ioctl() в Python поддерживает только SIO_RCVALL /
        SIO_KEEPALIVE_VALS / SIO_LOOPBACK_FAST_PATH — это захардкожено
        в реализации на C, SIO_UDP_CONNRESET через него не пройдёт.
        """
        import ctypes

        SIO_UDP_CONNRESET = 0x9800000C  # _WSAIOW(IOC_VENDOR, 12)

        ws2_32 = ctypes.WinDLL("ws2_32")
        in_buf = ctypes.c_bool(False)
        bytes_returned = ctypes.c_ulong(0)

        ret = ws2_32.WSAIoctl(
            sock.fileno(),
            SIO_UDP_CONNRESET,
            ctypes.byref(in_buf), ctypes.sizeof(in_buf),
            None, 0,
            ctypes.byref(bytes_returned),
            None, None,
        )
        if ret != 0:
            err = ctypes.windll.ws2_32.WSAGetLastError()
            raise OSError(f"WSAIoctl(SIO_UDP_CONNRESET) failed, WSAGetLastError={err}")

    @staticmethod
    def _make_socket(host: str, port: int) -> socket.socket:
        """
        Создаём и биндим сокет сами (вместо local_addr=), чтобы на Windows
        успеть отключить SIO_UDP_CONNRESET до первого recv.

        Без этого ProactorEventLoop матчит пришедший ICMP
        Host/Port Unreachable от ЛЮБОГО из пиров с текущей recv-операцией
        на сокете (WinError 1231 / 10054) — а у Endpoint один сокет на
        много Connection, так что ошибка от одного адреса может
        застопорить приём от остальных, пока сокет не пересоздан.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if sys.platform == "win32":
            try:
                Endpoint._disable_udp_connreset(sock)
            except OSError as exc:
                log.warning("Could not disable SIO_UDP_CONNRESET: %s", exc)
        sock.bind((host, port))
        sock.setblocking(False)
        return sock

    # ====================================================================== API

    def connect(self, remote_addr: tuple) -> Connection:
        addr = (remote_addr[0], remote_addr[1])
        if addr in self._connections:
            return self._connections[addr]
        conn = Connection(remote_addr=addr, transport=self._transport, loop=self._loop)
        conn.start()
        self._connections[addr] = conn
        log.info("Connected to %s", addr)
        return conn

    async def accept(self) -> Connection:
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
            conn = Connection(remote_addr=addr, transport=self._transport, loop=self._loop)
            conn.start()
            self._connections[addr] = conn
            log.info("New connection from %s", addr)
            self._new_conn_queue.put_nowait(conn)

        self._connections[addr].packet_received(pkt)

    def _on_error(self, exc: Exception) -> None:
        log.warning("UDP error: %s", exc)

    def __repr__(self) -> str:
        return f"Endpoint(conns={len(self._connections)}, addr={self.local_addr})"