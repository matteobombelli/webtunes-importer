"""Apple Music metadata via the keyless iTunes API + public web player.

Apple Music tracks are DRM-locked, so - like Spotify - we only read metadata and
resolve each track to YouTube. Albums and individual songs come from Apple's
keyless iTunes Lookup API. Playlists (pl.* ids) are absent from that API, so they
go through the amp-api the web player uses, authorized with a bearer token scraped
at runtime from the player's JS bundle (it rotates roughly monthly).
"""

import base64
import json
import re
import urllib.parse
import urllib.request

from webtunes_importer.core.models import TrackMeta

ITUNES_LOOKUP = "https://itunes.apple.com/lookup"


def _am_get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def _am_parse(url):
    """(kind, storefront, item_id) from an Apple Music URL, where kind is
    "playlist" | "album" | "song". A song is an album URL carrying ?i= (the song's
    id) or a /song/ URL; storefront defaults to "us" when the path omits it."""
    sf = re.search(r"music\.apple\.com/([a-z]{2})/", url)
    storefront = sf.group(1) if sf else "us"
    song = re.search(r"[?&]i=(\d+)", url)
    if song:
        return "song", storefront, song.group(1)
    pl = re.search(r"/playlist/[^/]*/(pl\.[A-Za-z0-9]+)", url)
    if pl:
        return "playlist", storefront, pl.group(1)
    album = re.search(r"/album/[^/]*/(\d+)", url)
    if album:
        return "album", storefront, album.group(1)
    sng = re.search(r"/song/(\d+)", url)
    if sng:
        return "song", storefront, sng.group(1)
    raise RuntimeError("Unrecognized Apple Music URL")


def _am_token():
    """Scrape the web player's anonymous bearer JWT. The JS bundle ships two JWTs;
    the amp-api one is issued by "AMPWebPlay"."""
    html = _am_get("https://music.apple.com/us/browse").decode("utf-8", "replace")
    m = re.search(r'/assets/index~[^"\']+\.js', html)
    if not m:
        raise RuntimeError("Could not locate Apple Music web player bundle")
    js = _am_get(f"https://music.apple.com{m.group(0)}").decode("utf-8", "replace")
    for tok in re.findall(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", js):
        payload = tok.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # restore base64 padding
        try:
            if json.loads(base64.urlsafe_b64decode(payload)).get("iss") == "AMPWebPlay":
                return tok
        except Exception:
            continue
    raise RuntimeError("Could not extract Apple Music web player token")


def _am_artwork(url):
    """Concrete 1200px cover URL from an Apple artwork reference - either an
    amp-api {w}x{h} template or an iTunes 100x100 thumbnail."""
    return (
        (url or "")
        .replace("{w}", "1200")
        .replace("{h}", "1200")
        .replace("100x100bb", "1200x1200bb")
    )


def _am_playlist_tracks(storefront, playlist_id):
    headers = {"Authorization": f"Bearer {_am_token()}", "Origin": "https://music.apple.com"}
    tracks = []
    path = f"/v1/catalog/{storefront}/playlists/{playlist_id}/tracks?limit=100&offset=0"
    while path:
        data = json.loads(_am_get(f"https://amp-api.music.apple.com{path}", headers))
        for item in data.get("data", []):
            a = item.get("attributes") or {}
            if not a.get("name"):
                continue
            tracks.append(TrackMeta(
                artist=a.get("artistName", ""),
                title=a["name"],
                album=a.get("albumName", ""),
                art_url=_am_artwork((a.get("artwork") or {}).get("url", "")),
                duration=(a.get("durationInMillis") or 0) / 1000,
            ))
        path = data.get("next")
    return tracks


def _itunes_tracks(item_id, entity=None):
    params = {"id": item_id}
    if entity:
        params.update(entity=entity, limit=200)
    data = json.loads(_am_get(f"{ITUNES_LOOKUP}?{urllib.parse.urlencode(params)}"))
    return [TrackMeta(
        artist=r.get("artistName", ""),
        title=r.get("trackName", ""),
        album=r.get("collectionName", ""),
        art_url=_am_artwork(r.get("artworkUrl100", "")),
        duration=(r.get("trackTimeMillis") or 0) / 1000,
    ) for r in data.get("results", []) if r.get("wrapperType") == "track"]


def apple_music_tracks(url) -> list[TrackMeta]:
    kind, storefront, item_id = _am_parse(url)
    if kind == "playlist":
        return _am_playlist_tracks(storefront, item_id)
    if kind == "album":
        return _itunes_tracks(item_id, entity="song")
    return _itunes_tracks(item_id)  # single song
