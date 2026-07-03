import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from webtunes_importer.core.webtunes import (
    AuthRevokedError,
    DuplicateTrackError,
    PairError,
    WebTunesClient,
)

VALID_CODE = "ABCD2345"
VALID_TOKEN = "wtx_testtoken"


class StubHandler(BaseHTTPRequestHandler):
    """Implements just enough of WebTunes' extension API for the client tests.
    Requests are recorded on the server object for assertions."""

    def log_message(self, *args):
        pass

    def _reply(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authed(self):
        return self.headers.get("Authorization") == f"Bearer {VALID_TOKEN}"

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.requests.append(("POST", self.path, dict(self.headers), body))
        if self.path == "/base/api/extension/pair":
            data = json.loads(body)
            if data.get("code") == VALID_CODE:
                self._reply(201, {"token": VALID_TOKEN, "userName": "Matteo"})
            else:
                self._reply(400, {"error": "Invalid or expired pairing code"})
        elif self.path == "/base/api/tracks/extension-import":
            if not self._authed():
                self._reply(401, {"error": "unauthorized"})
            elif self.server.duplicate_mode:
                self._reply(409, {"error": "That track is already in your library"})
            else:
                self._reply(201, {"id": "track-1", "title": "ok"})
        else:
            self._reply(404, {"error": "not found"})

    def do_GET(self):
        self.server.requests.append(("GET", self.path, dict(self.headers), b""))
        if self.path == "/base/api/extension/me":
            if self._authed():
                self._reply(200, {"userName": "Matteo"})
            else:
                self._reply(401, {"error": "unauthorized"})
        else:
            self._reply(404, {"error": "not found"})

    def do_DELETE(self):
        self.server.requests.append(("DELETE", self.path, dict(self.headers), b""))
        self._reply(204, {})


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), StubHandler)
    httpd.requests = []
    httpd.duplicate_mode = False
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()


def _client(server, token=None):
    return WebTunesClient(f"http://127.0.0.1:{server.server_port}/base/", token=token)


def test_pair_success_stores_token(server):
    client = _client(server)
    token, user = client.pair(VALID_CODE)
    assert token == VALID_TOKEN
    assert user == "Matteo"
    assert client.token == VALID_TOKEN
    method, path, headers, body = server.requests[0]
    sent = json.loads(body)
    assert sent["code"] == VALID_CODE
    assert sent["label"].startswith("WebTunes Importer on ")


def test_pair_bad_code_surfaces_server_message(server):
    with pytest.raises(PairError, match="Invalid or expired pairing code"):
        _client(server).pair("WRONG123")


def test_verify_ok(server):
    assert _client(server, VALID_TOKEN).verify() == "Matteo"


def test_verify_revoked(server):
    with pytest.raises(AuthRevokedError):
        _client(server, "wtx_revoked").verify()


def test_disconnect_never_raises_and_clears_token(server):
    client = _client(server, VALID_TOKEN)
    client.disconnect()
    assert client.token is None
    # even against a dead server
    dead = WebTunesClient("http://127.0.0.1:1/base", token="wtx_x", timeout=0.2)
    dead.disconnect()
    assert dead.token is None


def test_upload_sends_multipart_fields(server, tmp_path):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"ID3fakeaudio")
    client = _client(server, VALID_TOKEN)
    dto = client.upload_track(
        str(audio),
        source_url="https://youtu.be/x",
        title="Song",
        artist="Artist",
        album="Album",
        art_url="https://img/x.jpg",
        art_crop_square=True,
    )
    assert dto["id"] == "track-1"
    method, path, headers, body = server.requests[-1]
    assert headers["Authorization"] == f"Bearer {VALID_TOKEN}"
    assert b'name="file"; filename="song.mp3"' in body
    assert b"ID3fakeaudio" in body
    for field, value in [
        (b"sourceUrl", b"https://youtu.be/x"),
        (b"title", b"Song"),
        (b"artist", b"Artist"),
        (b"album", b"Album"),
        (b"artUrl", b"https://img/x.jpg"),
        (b"artCropSquare", b"1"),
    ]:
        assert b'name="' + field + b'"' in body
        assert value in body


def test_upload_omits_empty_fields(server, tmp_path):
    audio = tmp_path / "song.opus"
    audio.write_bytes(b"OggS")
    _client(server, VALID_TOKEN).upload_track(str(audio))
    body = server.requests[-1][3]
    assert b'name="artCropSquare"' not in body
    assert b'name="title"' not in body


def test_upload_duplicate(server, tmp_path):
    server.duplicate_mode = True
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"x")
    with pytest.raises(DuplicateTrackError):
        _client(server, VALID_TOKEN).upload_track(str(audio))


def test_upload_revoked(server, tmp_path):
    audio = tmp_path / "song.mp3"
    audio.write_bytes(b"x")
    with pytest.raises(AuthRevokedError):
        _client(server, "wtx_revoked").upload_track(str(audio))
