"""Live camera: the P1S serves JPEG frames over TLS on port 6000.

Protocol (community-documented, not official): after the TLS handshake the client sends an
80-byte auth packet; the printer then streams frames, each a 16-byte header whose first
4 bytes are the little-endian JPEG size, followed by the JPEG itself.
"""
from __future__ import annotations

import socket
import ssl
import struct
import threading
from typing import Callable

PORT = 6000
HEADER_SIZE = 16
MAX_FRAME = 5 * 1024 * 1024


class ProtocolError(Exception):
    pass


def auth_packet(access_code: str, user: str = "bblp") -> bytes:
    return (struct.pack("<IIII", 0x40, 0x3000, 0, 0)
            + user.encode().ljust(32, b"\0")[:32]
            + access_code.encode().ljust(32, b"\0")[:32])


class FrameParser:
    """Reassembles JPEG frames from an arbitrary chunking of the byte stream."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._need: int | None = None

    def feed(self, data: bytes) -> list[bytes]:
        self._buf += data
        frames: list[bytes] = []
        while True:
            if self._need is None:
                if len(self._buf) < HEADER_SIZE:
                    break
                size = struct.unpack_from("<I", self._buf, 0)[0]
                if size == 0 or size > MAX_FRAME:
                    raise ProtocolError(f"implausible frame size {size}")
                del self._buf[:HEADER_SIZE]
                self._need = size
            if len(self._buf) < self._need:
                break
            frame = bytes(self._buf[: self._need])
            del self._buf[: self._need]
            self._need = None
            if not (frame.startswith(b"\xff\xd8") and frame.endswith(b"\xff\xd9")):
                raise ProtocolError("frame is not a complete JPEG")
            frames.append(frame)
        return frames


class CameraClient:
    def __init__(self, ip: str, access_code: str, on_frame: Callable[[bytes], None],
                 port: int = PORT, timeout: float = 10.0):
        self.ip, self.access_code, self.port, self.timeout = ip, access_code, port, timeout
        self.on_frame = on_frame
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        """Blocking read loop. Raises OSError/ProtocolError on failure; returns when stopped."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # self-signed printer certificate
        parser = FrameParser()
        with socket.create_connection((self.ip, self.port), timeout=self.timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=self.ip) as sock:
                sock.settimeout(self.timeout)
                sock.sendall(auth_packet(self.access_code))
                while not self._stop.is_set():
                    try:
                        data = sock.recv(65536)
                    except socket.timeout:
                        continue
                    if not data:
                        raise ConnectionError("camera closed the connection")
                    for frame in parser.feed(data):
                        self.on_frame(frame)
