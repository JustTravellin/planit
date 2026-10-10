"""Upload files to the printer over implicit FTPS (port 990, user "bblp")."""
from __future__ import annotations

import ftplib
import socket
import ssl
from pathlib import Path
from typing import Callable


class _ImplicitFtpTls(ftplib.FTP_TLS):
    """FTP_TLS that wraps the control connection in TLS immediately (implicit mode)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sock = None

    @property
    def sock(self):
        return self._sock

    @sock.setter
    def sock(self, value):
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value, server_hostname=self.host)
        self._sock = value

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            # Reuse the control channel's TLS session; the printer requires it.
            conn = self.context.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
        return conn, size


def upload(ip: str, access_code: str, local_path: str | Path, remote_name: str | None = None, timeout: float = 30.0,
           progress: Callable[[int, int], None] | None = None) -> str:
    """Upload a file to the printer and return the remote file name."""
    local_path = Path(local_path)
    remote_name = remote_name or local_path.name
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # self-signed printer certificate
    ftp = _ImplicitFtpTls(context=ctx)
    ftp.connect(ip, 990, timeout=timeout)
    try:
        ftp.login("bblp", access_code)
        ftp.prot_p()
        total = local_path.stat().st_size
        sent = 0

        def _cb(chunk: bytes) -> None:
            nonlocal sent
            sent += len(chunk)
            if progress:
                progress(sent, total)

        with local_path.open("rb") as fh:
            ftp.storbinary(f"STOR {remote_name}", fh, callback=_cb)
    finally:
        try:
            ftp.quit()
        except (OSError, ftplib.Error, socket.timeout):
            ftp.close()
    return remote_name
