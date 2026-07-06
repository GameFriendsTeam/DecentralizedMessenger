"""
Stream — per-stream state machine.

Each stream has:
  - Independent sequence counter (send side)
  - Independent expected_seq (receive side)
  - Reorder buffer for reliable+ordered streams
  - Delivery queue: asyncio.Queue that the user awaits on

SYN semantics:
  - open_stream() создаёт стрим локально, но НЕ уведомляет удалённую сторону
  - stream.sync() отправляет SYN-пакет — удалённая сторона создаёт стрим немедленно
  - conn.get_stream(id) — async, ждёт SYN если стрим ещё не известен
"""

import asyncio
from enum import Enum, auto
from typing import Callable

from .packet import Flags, Packet


class StreamState(Enum):
    OPEN    = auto()
    CLOSING = auto()
    CLOSED  = auto()


class Stream:
    """
    Represents one logical channel inside a Connection.

    Parameters
    ----------
    stream_id  : uint16 identifier
    reliable   : whether packets on this stream need ACK/retransmit
    ordered    : whether packets must be delivered in seq order
    send_fn    : coroutine that physically sends a Packet (provided by Connection)
    """

    def __init__(
        self,
        stream_id: int,
        reliable: bool,
        ordered: bool,
        send_fn: Callable,
    ) -> None:
        self.stream_id = stream_id
        self.reliable  = reliable
        self.ordered   = ordered
        self._send_fn  = send_fn

        self.state = StreamState.OPEN

        # send side
        self._send_seq: int = 0

        # receive side
        self._recv_seq: int = 0                   # next expected seq
        self._reorder_buf: dict[int, bytes] = {}  # seq -> payload (reliable+ordered)
        self._seen_seqs: set[int] = set()         # dedup for reliable+unordered

        # delivery
        self._recv_queue: asyncio.Queue[bytes] = asyncio.Queue()

    # ===================================================================== send

    async def sync(self) -> None:
        """
        Announce this stream to the remote side by sending a SYN packet.
        The remote's get_stream(id) will unblock as soon as SYN arrives.

        Call this after open_stream() if you want the remote to know about
        the stream before any data is sent.
        """
        if self.state != StreamState.OPEN:
            raise RuntimeError("Stream is not open")

        flags = Flags.SYN
        if self.reliable:
            flags |= Flags.REL

        pkt = Packet(
            stream_id=self.stream_id,
            seq=self._send_seq,   # seq не продвигаем — SYN не данные
            ack=0,
            flags=flags,
            payload=b"",
        )
        await self._send_fn(pkt)

    async def send(self, data: bytes) -> None:
        """Send data on this stream."""
        if self.state != StreamState.OPEN:
            raise RuntimeError("Stream is not open")

        flags = Flags.NONE
        if self.reliable:
            flags |= Flags.REL
        if self.ordered:
            flags |= Flags.ORD

        pkt = Packet(
            stream_id=self.stream_id,
            seq=self._send_seq,
            ack=0,
            flags=flags,
            payload=data,
        )
        self._send_seq = (self._send_seq + 1) & 0xFFFF_FFFF
        await self._send_fn(pkt)

    # ================================================================== receive

    def receive_packet(self, pkt: Packet) -> None:
        """
        Called by Connection when a packet arrives for this stream.
        SYN packets are ignored here (handled in Connection.packet_received).
        """
        if self.state == StreamState.CLOSED:
            return

        if Flags.FIN in pkt.flags:
            self.state = StreamState.CLOSED
            return

        # SYN без данных — это просто объявление стрима, данных нет
        if Flags.SYN in pkt.flags and not pkt.payload:
            return

        payload = pkt.payload
        if not payload:
            return  # ACK-only

        seq = pkt.seq

        if not self.ordered:
            # Unordered — deliver immediately, dedup reliable retransmits
            if self.reliable:
                if seq in self._seen_seqs:
                    return
                self._seen_seqs.add(seq)
                if len(self._seen_seqs) > 1024:
                    self._seen_seqs.discard(min(self._seen_seqs))
            self._recv_queue.put_nowait(payload)
            return

        if not self.reliable:
            # Ordered + unreliable: drop stale, deliver fresh
            if _seq_gt(seq, self._recv_seq) or seq == self._recv_seq:
                self._recv_seq = (seq + 1) & 0xFFFF_FFFF
                self._recv_queue.put_nowait(payload)
            return

        # Reliable + ordered: buffer out-of-order, flush in order
        if seq == self._recv_seq:
            self._recv_queue.put_nowait(payload)
            self._recv_seq = (self._recv_seq + 1) & 0xFFFF_FFFF
            self._flush_reorder_buf()
        elif _seq_gt(seq, self._recv_seq):
            self._reorder_buf[seq] = payload
        # else: duplicate / old — drop

    def _flush_reorder_buf(self) -> None:
        while self._recv_seq in self._reorder_buf:
            payload = self._reorder_buf.pop(self._recv_seq)
            self._recv_queue.put_nowait(payload)
            self._recv_seq = (self._recv_seq + 1) & 0xFFFF_FFFF

    # ================================================================= user API

    async def recv(self) -> bytes:
        """Wait for the next delivered payload."""
        if self.state == StreamState.CLOSED and self._recv_queue.empty():
            raise EOFError("Stream closed")
        return await self._recv_queue.get()

    def recv_nowait(self) -> bytes | None:
        try:
            return self._recv_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def close(self) -> None:
        """Send FIN and mark stream as closing."""
        if self.state != StreamState.OPEN:
            return
        self.state = StreamState.CLOSING
        flags = Flags.FIN
        if self.reliable:
            flags |= Flags.REL
        pkt = Packet(
            stream_id=self.stream_id,
            seq=self._send_seq,
            ack=0,
            flags=flags,
            payload=b"",
        )
        await self._send_fn(pkt)

    def __repr__(self) -> str:
        mode = []
        if self.reliable:
            mode.append("reliable")
        if self.ordered:
            mode.append("ordered")
        return (
            f"Stream(id={self.stream_id}, "
            f"mode={'|'.join(mode) or 'unreliable+unordered'}, "
            f"state={self.state.name})"
        )


# --------------------------------------------------------------------------- util

def _seq_gt(a: int, b: int) -> bool:
    """Sequence number comparison with wrap-around (RFC 1982 style). a > b?"""
    if a == b:
        return False
    return ((a - b) & 0xFFFF_FFFF) < 0x8000_0000
