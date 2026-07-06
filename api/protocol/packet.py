"""
Packet definitions.

Header layout (16 bytes):
  1B version | 1B flags | 2B stream_id | 4B seq | 4B ack | 2B length | 2B checksum
"""

import struct
import zlib
from dataclasses import dataclass, field
from enum import IntFlag

HEADER_FORMAT = "!BBHIIhH"  # network byte order
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 16 bytes
VERSION = 1
MAX_PAYLOAD = 1200  # safe MTU under IPv4+UDP headers


class Flags(IntFlag):
    NONE = 0
    SYN  = 1 << 0   # open stream
    FIN  = 1 << 1   # close stream
    ACK  = 1 << 2   # packet carries ack
    RST  = 1 << 3   # reset connection
    REL  = 1 << 4   # reliable — needs ACK + retransmit
    ORD  = 1 << 5   # ordered delivery


@dataclass
class Packet:
    stream_id: int       # uint16
    seq:       int       # uint32
    ack:       int       # uint32  (0 if ACK flag not set)
    flags:     Flags
    payload:   bytes = field(default=b"")

    # ------------------------------------------------------------------ encode

    def encode(self) -> bytes:
        header = struct.pack(
            HEADER_FORMAT,
            VERSION,
            int(self.flags),
            self.stream_id,
            self.seq & 0xFFFF_FFFF,
            self.ack & 0xFFFF_FFFF,
            len(self.payload),
            0,              # checksum placeholder
        )
        data = header + self.payload
        checksum = zlib.crc32(data) & 0xFFFF
        # patch checksum into bytes 14-15
        return data[:14] + struct.pack("!H", checksum) + data[16:]

    # ------------------------------------------------------------------ decode

    @classmethod
    def decode(cls, data: bytes) -> "Packet":
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Too short: {len(data)} bytes")

        version, raw_flags, stream_id, seq, ack, length, checksum = struct.unpack(
            HEADER_FORMAT, data[:HEADER_SIZE]
        )

        if version != VERSION:
            raise ValueError(f"Unknown version: {version}")

        # verify checksum
        patched = data[:14] + b"\x00\x00" + data[16:]
        expected = zlib.crc32(patched) & 0xFFFF
        if checksum != expected:
            raise ValueError("Checksum mismatch")

        payload = data[HEADER_SIZE : HEADER_SIZE + length]
        if len(payload) != length:
            raise ValueError("Truncated payload")

        return cls(
            stream_id=stream_id,
            seq=seq,
            ack=ack,
            flags=Flags(raw_flags),
            payload=payload,
        )

    # ------------------------------------------------------------------ helpers

    def is_reliable(self) -> bool:
        return Flags.REL in self.flags

    def is_ordered(self) -> bool:
        return Flags.ORD in self.flags

    def __repr__(self) -> str:
        return (
            f"Packet(stream={self.stream_id}, seq={self.seq}, ack={self.ack}, "
            f"flags={self.flags!s}, payload={len(self.payload)}B)"
        )
