import shutil
import socket
import ssl
import struct
import subprocess
import threading

import pytest

from p1s_controller import camera
from p1s_controller.connection_test import check_connection

JPEG1 = b"\xff\xd8" + b"A" * 50 + b"\xff\xd9"
JPEG2 = b"\xff\xd8" + b"B" * 10 + b"\xff\xd9"


def framed(jpeg):
    return struct.pack("<IIII", len(jpeg), 0, 0, 0) + jpeg


def test_auth_packet_layout():
    p = camera.auth_packet("12345678")
    assert len(p) == 80
    assert struct.unpack_from("<IIII", p) == (0x40, 0x3000, 0, 0)
    assert p[16:20] == b"bblp" and p[48:56] == b"12345678"


def test_parser_handles_arbitrary_chunking():
    stream = framed(JPEG1) + framed(JPEG2)
    p = camera.FrameParser()
    out = []
    for i in range(0, len(stream), 7):  # tiny chunks, splits headers and payloads
        out += p.feed(stream[i:i + 7])
    assert out == [JPEG1, JPEG2]


def test_parser_rejects_bad_data():
    with pytest.raises(camera.ProtocolError):
        camera.FrameParser().feed(struct.pack("<IIII", 0, 0, 0, 0))
    with pytest.raises(camera.ProtocolError):
        camera.FrameParser().feed(struct.pack("<IIII", 4, 0, 0, 0) + b"nope")


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not available")
def test_client_against_fake_tls_server(tmp_path):
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
                    "-out", str(cert), "-subj", "/CN=printer", "-days", "1"], check=True, capture_output=True)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    received = {}

    def serve():
        conn, _ = server.accept()
        with ctx.wrap_socket(conn, server_side=True) as tls:
            buf = b""
            while len(buf) < 80:
                buf += tls.recv(80 - len(buf))
            received["auth"] = buf
            tls.sendall(framed(JPEG1) + framed(JPEG2))
            tls.recv(1)  # wait for client to hang up

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    frames = []
    done = threading.Event()
    client = camera.CameraClient("127.0.0.1", "secretco", lambda f: (frames.append(f), len(frames) == 2 and done.set()),
                                 port=port, timeout=2)
    runner = threading.Thread(target=client.run, daemon=True)
    runner.start()
    assert done.wait(5)
    client.stop()
    runner.join(5)
    assert frames == [JPEG1, JPEG2]
    assert received["auth"] == camera.auth_packet("secretco")
    server.close()


def test_connection_test_reports_unreachable_printer():
    # nothing listens on 8883 locally, so this must fail fast with a helpful message
    ok, message = check_connection("127.0.0.1", "SERIAL", "code", timeout=1)
    assert not ok and "Can't reach" in message and "LAN Only Mode" in message
