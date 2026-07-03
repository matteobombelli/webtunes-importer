"""HTTP client for WebTunes' extension pairing and import API.

Mirrors the browser extension's protocol exactly:
  POST   /api/extension/pair            {code, label} -> {token, userName}
  GET    /api/extension/me              Bearer -> {userName}; 401 = revoked
  DELETE /api/extension/me              Bearer, best-effort self-revoke
  POST   /api/tracks/extension-import   Bearer, multipart -> TrackDTO
"""

import platform
from pathlib import Path

import requests

from webtunes_importer.constants import DEFAULT_SERVER_URL, MAX_UPLOAD_BYTES


class PairError(Exception):
    """Pairing failed with a message the UI can show as-is."""


class AuthRevokedError(Exception):
    """The server rejected our token (401) - the connection was revoked."""


class DuplicateTrackError(Exception):
    """The track already exists in the user's WebTunes library (409)."""


def normalize_server_url(raw: str) -> str:
    url = (raw or "").strip().rstrip("/")
    return url or DEFAULT_SERVER_URL


def pairing_label() -> str:
    system = {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}.get(
        platform.system(), platform.system() or "unknown OS"
    )
    return f"WebTunes Importer on {system}"


def _error_message(resp, fallback):
    try:
        return resp.json().get("error") or fallback
    except ValueError:
        return fallback


class WebTunesClient:
    def __init__(self, server_url: str, token: str | None = None, timeout: float = 30):
        self.server_url = normalize_server_url(server_url)
        self.token = token
        self.timeout = timeout

    def _api(self, path: str) -> str:
        return f"{self.server_url}/api{path}"

    def _auth_headers(self) -> dict:
        if not self.token:
            raise AuthRevokedError("not connected")
        return {"Authorization": f"Bearer {self.token}"}

    def pair(self, code: str, label: str | None = None) -> tuple[str, str | None]:
        """Redeem a pairing code. Returns (token, userName) and stores the token
        on this client. Raises PairError with a user-facing message on failure."""
        resp = requests.post(
            self._api("/extension/pair"),
            json={"code": code.strip(), "label": label or pairing_label()},
            timeout=self.timeout,
        )
        if not resp.ok:
            raise PairError(_error_message(resp, f"Pairing failed (HTTP {resp.status_code})"))
        body = resp.json()
        self.token = body["token"]
        return body["token"], body.get("userName")

    def verify(self) -> str | None:
        """Check the stored token. Returns the (possibly refreshed) user name.
        Raises AuthRevokedError on 401; network errors propagate as
        requests.ConnectionError et al. (offline is not disconnected)."""
        resp = requests.get(
            self._api("/extension/me"), headers=self._auth_headers(), timeout=self.timeout
        )
        if resp.status_code == 401:
            raise AuthRevokedError()
        resp.raise_for_status()
        return resp.json().get("userName")

    def disconnect(self) -> None:
        """Best-effort server-side revoke; never raises."""
        try:
            requests.delete(
                self._api("/extension/me"), headers=self._auth_headers(), timeout=self.timeout
            )
        except Exception:
            pass
        self.token = None

    def upload_track(
        self,
        path: str,
        *,
        source_url: str | None = None,
        title: str | None = None,
        artist: str | None = None,
        album: str | None = None,
        art_url: str | None = None,
        art_crop_square: bool = False,
    ) -> dict:
        """Upload one audio file. Returns the created TrackDTO.

        Raises DuplicateTrackError (409), AuthRevokedError (401), or
        RuntimeError with the server's message otherwise."""
        p = Path(path)
        if p.stat().st_size > MAX_UPLOAD_BYTES:
            raise RuntimeError("file exceeds WebTunes' 100 MB upload limit")

        fields = {}
        if source_url:
            fields["sourceUrl"] = source_url
        if title:
            fields["title"] = title
        if artist:
            fields["artist"] = artist
        if album:
            fields["album"] = album
        if art_url:
            fields["artUrl"] = art_url
        if art_crop_square:
            fields["artCropSquare"] = "1"

        with p.open("rb") as f:
            resp = requests.post(
                self._api("/tracks/extension-import"),
                headers=self._auth_headers(),
                files={"file": (p.name, f)},
                data=fields,
                timeout=max(self.timeout, 300),  # uploads can be slow
            )
        if resp.status_code == 401:
            raise AuthRevokedError()
        if resp.status_code == 409:
            raise DuplicateTrackError(_error_message(resp, "already in WebTunes"))
        if not resp.ok:
            raise RuntimeError(_error_message(resp, f"upload failed (HTTP {resp.status_code})"))
        return resp.json()
