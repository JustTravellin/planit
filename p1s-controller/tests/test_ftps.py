import io

from p1s_controller import ftps


class FakeConn:
    def __init__(self):
        self.data, self.unwrapped = b"", False
    def sendall(self, b): self.data += b
    def unwrap(self): self.unwrapped = True  # must never be called: the printer doesn't answer close_notify
    def __enter__(self): return self
    def __exit__(self, *a): pass


def test_storbinary_sends_everything_and_never_unwraps():
    ftp = ftps._ImplicitFtpTls.__new__(ftps._ImplicitFtpTls)
    conn, calls = FakeConn(), []
    ftp.voidcmd = lambda c: calls.append(c)
    ftp.transfercmd = lambda c, rest=None: conn
    ftp.voidresp = lambda: "226"
    seen = []
    assert ftp.storbinary("STOR a", io.BytesIO(b"x" * 20000), 8192, seen.append) == "226"
    assert len(conn.data) == 20000 and sum(map(len, seen)) == 20000 and not conn.unwrapped and calls == ["TYPE I"]
