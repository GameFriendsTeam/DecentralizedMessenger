"""
MTP Connection — multiplexer over a single UDP path.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from .packet import Flags, Packet
from .stream import Stream

log = logging.getLogger("mtp.connection")

RETRANSMIT_TIMEOUT = 0.200
MAX_RETRANSMITS    = 8
ACK_DELAY          = 0.010


@dataclass
class _PendingPacket:
    pkt:       Packet
    stream_id: int
    seq:       int
    deadline:  float
    attempts:  int = 0


class Connection:
    def __init__(self, remote_addr: tuple, transport: Any, loop: asyncio.AbstractEventLoop) -> None:
        self.remote_addr  = remote_addr
        self._transport   = transport
        self._loop        = loop          # явно передаём loop
        self._streams:    dict[int, Stream] = {}
        self._pending:    dict[tuple, _PendingPacket] = {}
        self._ack_pending: dict[int, int] = {}
        self._ack_task:   asyncio.Task | None = None
        self._stream_waiters: dict[int, list[asyncio.Future]] = {}
        self._retransmit_task: asyncio.Task | None = None
        self._closed = False

    # ====================================================================== API

    def open_stream(self, stream_id: int, reliable: bool = True, ordered: bool = True) -> Stream:
        if stream_id in self._streams:
            raise ValueError(f"Stream {stream_id} already open")
        stream = Stream(
            stream_id=stream_id,
            reliable=reliable,
            ordered=ordered,
            send_fn=self._send_packet,
        )
        self._streams[stream_id] = stream
        return stream

    async def get_stream(self, stream_id: int) -> Stream:
        if stream_id in self._streams:
            return self._streams[stream_id]
        fut: asyncio.Future[Stream] = self._loop.create_future()
        self._stream_waiters.setdefault(stream_id, []).append(fut)
        log.debug("Waiting for SYN on stream %d from %s", stream_id, self.remote_addr)
        return await fut

    def start(self) -> None:
        # используем loop.create_task() — работает из любого потока
        self._retransmit_task = self._loop.create_task(self._retransmit_loop())

    async def close(self) -> None:
        self._closed = True
        if self._retransmit_task:
            self._retransmit_task.cancel()
        if self._ack_task:
            self._ack_task.cancel()
        for futs in self._stream_waiters.values():
            for fut in futs:
                if not fut.done():
                    fut.cancel()
        for stream in self._streams.values():
            await stream.close()

    # ================================================================= send

    async def _send_packet(self, pkt: Packet) -> None:
        if pkt.stream_id in self._ack_pending:
            pkt.ack   = self._ack_pending.pop(pkt.stream_id)
            pkt.flags |= Flags.ACK

        data = pkt.encode()
        self._transport.sendto(data, self.remote_addr)

        if pkt.is_reliable() and pkt.payload:
            key = (pkt.stream_id, pkt.seq)
            self._pending[key] = _PendingPacket(
                pkt=pkt,
                stream_id=pkt.stream_id,
                seq=pkt.seq,
                deadline=time.monotonic() + RETRANSMIT_TIMEOUT,
            )

    async def _send_ack(self, stream_id: int, ack_seq: int) -> None:
        pkt = Packet(stream_id=stream_id, seq=0, ack=ack_seq, flags=Flags.ACK, payload=b"")
        self._transport.sendto(pkt.encode(), self.remote_addr)

    # ============================================================= dispatch

    def packet_received(self, pkt: Packet) -> None:
        if Flags.ACK in pkt.flags:
            self._process_ack(pkt.stream_id, pkt.ack)

        if Flags.SYN in pkt.flags:
            self._handle_syn(pkt)
            if not pkt.payload:
                return

        if pkt.is_reliable() and pkt.payload:
            self._ack_pending[pkt.stream_id] = pkt.seq
            self._schedule_ack_flush()

        stream = self._streams.get(pkt.stream_id)
        if stream:
            stream.receive_packet(pkt)
        elif pkt.payload:
            stream = Stream(
                stream_id=pkt.stream_id,
                reliable=pkt.is_reliable(),
                ordered=pkt.is_ordered(),
                send_fn=self._send_packet,
            )
            self._streams[pkt.stream_id] = stream
            stream.receive_packet(pkt)

    def _handle_syn(self, pkt: Packet) -> None:
        sid = pkt.stream_id
        if sid not in self._streams:
            stream = Stream(
                stream_id=sid,
                reliable=pkt.is_reliable(),
                ordered=pkt.is_ordered(),
                send_fn=self._send_packet,
            )
            self._streams[sid] = stream
            log.debug("SYN: created stream %d from %s", sid, self.remote_addr)
        else:
            stream = self._streams[sid]

        for fut in self._stream_waiters.pop(sid, []):
            if not fut.done():
                fut.set_result(stream)

    def _process_ack(self, stream_id: int, ack_seq: int) -> None:
        key = (stream_id, ack_seq)
        if key in self._pending:
            del self._pending[key]

    # ============================================================= retransmit

    async def _retransmit_loop(self) -> None:
        while not self._closed:
            await asyncio.sleep(0.050)
            now = time.monotonic()
            dead = []
            for key, pp in list(self._pending.items()):
                if now >= pp.deadline:
                    if pp.attempts >= MAX_RETRANSMITS:
                        dead.append(key)
                        continue
                    pp.attempts += 1
                    pp.deadline  = now + RETRANSMIT_TIMEOUT * (1.5 ** pp.attempts)
                    self._transport.sendto(pp.pkt.encode(), self.remote_addr)
            for key in dead:
                del self._pending[key]

    # ================================================================= ACK delay

    def _schedule_ack_flush(self) -> None:
        if self._ack_task is None or self._ack_task.done():
            # call_soon_threadsafe гарантирует что create_task выполнится в нужном loop
            self._loop.call_soon_threadsafe(
                lambda: self._loop.create_task(self._ack_flush_task())
            )

    async def _ack_flush_task(self) -> None:
        await asyncio.sleep(ACK_DELAY)
        for stream_id, ack_seq in list(self._ack_pending.items()):
            await self._send_ack(stream_id, ack_seq)
        self._ack_pending.clear()

    def __repr__(self) -> str:
        return f"Connection(remote={self.remote_addr}, streams={list(self._streams)})"
