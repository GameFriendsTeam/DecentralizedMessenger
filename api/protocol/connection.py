"""
CTP Connection — multiplexer over a single UDP path.

Responsibilities:
  - Owns a dict of Stream objects keyed by stream_id
  - Sends/receives raw packets via the transport (set by Endpoint)
  - ACK tracking: accumulates ACKs, sends them piggybacked or standalone
  - Retransmit: for reliable packets keeps an unACKed queue with deadlines
  - SYN handling: incoming SYN создаёт стрим и уведомляет ожидающих get_stream()
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .packet import Flags, Packet, MAX_PAYLOAD
from .stream import Stream

log = logging.getLogger("CTP.connection")

RETRANSMIT_TIMEOUT = 0.200   # seconds before retransmitting unACKed packet
MAX_RETRANSMITS    = 8
ACK_DELAY          = 0.010   # max delay before sending a standalone ACK (10 ms)


@dataclass
class _PendingPacket:
    """A reliable packet waiting for ACK."""
    pkt:       Packet
    stream_id: int
    seq:       int
    deadline:  float
    attempts:  int = 0


class Connection:
    """
    One logical connection to a remote (addr, port).
    Created and owned by Endpoint — not instantiated directly.
    """

    def __init__(self, remote_addr: tuple, transport: Any) -> None:
        self.remote_addr   = remote_addr
        self._transport    = transport
        self._streams:     dict[int, Stream] = {}

        # reliable send tracking  key=(stream_id, seq)
        self._pending:     dict[tuple, _PendingPacket] = {}

        # pending ACKs  key=stream_id -> seq
        self._ack_pending: dict[int, int] = {}
        self._ack_task:    asyncio.Task | None = None

        # get_stream() waiters: stream_id -> list of Futures
        # когда приходит SYN с этим stream_id — все Future резолвятся
        self._stream_waiters: dict[int, list[asyncio.Future]] = {}

        self._retransmit_task: asyncio.Task | None = None
        self._closed = False

    # ====================================================================== API

    def open_stream(
        self,
        stream_id: int,
        reliable: bool = True,
        ordered: bool = True,
    ) -> Stream:
        """
        Create a stream locally. Does NOT notify the remote side.
        Call stream.sync() to send SYN so the remote's get_stream() unblocks.
        """
        if stream_id in self._streams:
            raise ValueError(f"Stream {stream_id} already open")
        stream = Stream(
            stream_id=stream_id,
            reliable=reliable,
            ordered=ordered,
            send_fn=self._send_packet,
        )
        self._streams[stream_id] = stream
        log.debug("Opened %s on %s", stream, self.remote_addr)
        return stream

    async def get_stream(self, stream_id: int) -> Stream:
        """
        Return the stream if it exists, otherwise wait until a SYN arrives
        from the remote with this stream_id.

        Typical usage on the passive side:
            stream = await conn.get_stream(5)
            data = await stream.recv()
        """
        if stream_id in self._streams:
            return self._streams[stream_id]

        # Register a Future that will be resolved when SYN arrives
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Stream] = loop.create_future()
        self._stream_waiters.setdefault(stream_id, []).append(fut)
        log.debug("Waiting for SYN on stream %d from %s", stream_id, self.remote_addr)
        return await fut

    def start(self) -> None:
        self._retransmit_task = asyncio.ensure_future(self._retransmit_loop())

    async def close(self) -> None:
        self._closed = True
        if self._retransmit_task:
            self._retransmit_task.cancel()
        if self._ack_task:
            self._ack_task.cancel()
        # Cancel any pending get_stream() waiters
        for futs in self._stream_waiters.values():
            for fut in futs:
                if not fut.done():
                    fut.cancel()
        for stream in self._streams.values():
            await stream.close()

    # ================================================================= internal send

    async def _send_packet(self, pkt: Packet) -> None:
        """Encode and send; register reliable data packets for retransmit."""
        # Piggyback pending ACK for this stream
        if pkt.stream_id in self._ack_pending:
            pkt.ack   = self._ack_pending.pop(pkt.stream_id)
            pkt.flags |= Flags.ACK

        data = pkt.encode()
        self._transport.sendto(data, self.remote_addr)

        # Track for retransmit: only data packets (payload non-empty) that are reliable
        if pkt.is_reliable() and pkt.payload:
            key = (pkt.stream_id, pkt.seq)
            self._pending[key] = _PendingPacket(
                pkt=pkt,
                stream_id=pkt.stream_id,
                seq=pkt.seq,
                deadline=time.monotonic() + RETRANSMIT_TIMEOUT,
            )

    async def _send_ack(self, stream_id: int, ack_seq: int) -> None:
        pkt = Packet(
            stream_id=stream_id,
            seq=0,
            ack=ack_seq,
            flags=Flags.ACK,
            payload=b"",
        )
        self._transport.sendto(pkt.encode(), self.remote_addr)

    # ============================================================= packet dispatch

    def packet_received(self, pkt: Packet) -> None:
        """Called by Endpoint when a packet arrives for this connection."""

        # --- process ACK ---
        if Flags.ACK in pkt.flags:
            self._process_ack(pkt.stream_id, pkt.ack)

        # --- SYN: remote is announcing a new stream ---
        if Flags.SYN in pkt.flags:
            self._handle_syn(pkt)
            # SYN может нести данные — падаем через в обычный dispatch ниже
            if not pkt.payload:
                return

        # --- schedule ACK reply for reliable data packets ---
        if pkt.is_reliable() and pkt.payload:
            self._ack_pending[pkt.stream_id] = pkt.seq
            self._schedule_ack_flush()

        # --- deliver to stream ---
        stream = self._streams.get(pkt.stream_id)
        if stream:
            stream.receive_packet(pkt)
        elif pkt.payload:
            # Пакет с данными пришёл без предшествующего SYN —
            # автосоздаём стрим (обратная совместимость / unreliable streams)
            rel  = pkt.is_reliable()
            ord_ = pkt.is_ordered()
            stream = Stream(
                stream_id=pkt.stream_id,
                reliable=rel,
                ordered=ord_,
                send_fn=self._send_packet,
            )
            self._streams[pkt.stream_id] = stream
            log.debug("Auto-created stream %d (no prior SYN) from %s", pkt.stream_id, self.remote_addr)
            stream.receive_packet(pkt)

    def _handle_syn(self, pkt: Packet) -> None:
        """
        Create stream from incoming SYN and wake up any get_stream() waiters.
        Idempotent — safe if SYN is retransmitted.
        """
        sid = pkt.stream_id
        if sid not in self._streams:
            rel  = pkt.is_reliable()
            ord_ = pkt.is_ordered()
            stream = Stream(
                stream_id=sid,
                reliable=rel,
                ordered=ord_,
                send_fn=self._send_packet,
            )
            self._streams[sid] = stream
            log.debug("SYN: created stream %d from %s", sid, self.remote_addr)
        else:
            stream = self._streams[sid]

        # Wake up all get_stream() waiters for this id
        for fut in self._stream_waiters.pop(sid, []):
            if not fut.done():
                fut.set_result(stream)

    def _process_ack(self, stream_id: int, ack_seq: int) -> None:
        key = (stream_id, ack_seq)
        if key in self._pending:
            del self._pending[key]
            log.debug("ACKed stream=%d seq=%d", stream_id, ack_seq)

    # ============================================================= retransmit loop

    async def _retransmit_loop(self) -> None:
        while not self._closed:
            await asyncio.sleep(0.050)
            now = time.monotonic()
            dead = []
            for key, pp in list(self._pending.items()):
                if now >= pp.deadline:
                    if pp.attempts >= MAX_RETRANSMITS:
                        log.warning(
                            "Giving up on stream=%d seq=%d after %d retransmits",
                            pp.stream_id, pp.seq, pp.attempts,
                        )
                        dead.append(key)
                        continue
                    pp.attempts += 1
                    pp.deadline  = now + RETRANSMIT_TIMEOUT * (1.5 ** pp.attempts)
                    self._transport.sendto(pp.pkt.encode(), self.remote_addr)
                    log.debug("Retransmit stream=%d seq=%d attempt=%d",
                              pp.stream_id, pp.seq, pp.attempts)
            for key in dead:
                del self._pending[key]

    # ================================================================= ACK delay

    def _schedule_ack_flush(self) -> None:
        if self._ack_task is None or self._ack_task.done():
            self._ack_task = asyncio.ensure_future(self._ack_flush_task())

    async def _ack_flush_task(self) -> None:
        await asyncio.sleep(ACK_DELAY)
        for stream_id, ack_seq in list(self._ack_pending.items()):
            await self._send_ack(stream_id, ack_seq)
        self._ack_pending.clear()

    def __repr__(self) -> str:
        return f"Connection(remote={self.remote_addr}, streams={list(self._streams)})"
