"""Spotify metadata via the public web-player API - no credentials.

Spotify's documented Web API requires OAuth and 403s for newly created apps,
so we read metadata the way the public web player does: the embed page carries
an anonymous access token, which the web player's GraphQL ("pathfinder") API
accepts - including offset pagination, so playlists of any length work.
"""

import json
import re
import urllib.parse
import urllib.request
from collections.abc import Callable

from webtunes_importer.core.models import TrackMeta

PATHFINDER_URL = "https://api-partner.spotify.com/pathfinder/v1/query"
FETCH_PLAYLIST_HASH = "b39f62e9b566aa849b1780927de1450f47e02c54abf1e66e513f96e849591e41"


def _largest_image(images):
    """Pick the highest-resolution URL from a list of {url, width, height}."""
    best = max(images or [], key=lambda im: (im.get("width") or 0), default=None)
    return best["url"] if best else ""


def _embed_state(item_id, kind="playlist"):
    req = urllib.request.Request(
        f"https://open.spotify.com/embed/{kind}/{item_id}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode()
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S
    )
    if not m:
        raise RuntimeError("Could not read playlist from Spotify embed page")
    return json.loads(m.group(1))["props"]["pageProps"]["state"]


def _pathfinder_tracks(playlist_id, token):
    tracks, offset, total = [], 0, None
    while total is None or offset < total:
        params = urllib.parse.urlencode({
            "operationName": "fetchPlaylist",
            "variables": json.dumps(
                {"uri": f"spotify:playlist:{playlist_id}", "offset": offset, "limit": 100}),
            "extensions": json.dumps(
                {"persistedQuery": {"version": 1, "sha256Hash": FETCH_PLAYLIST_HASH}}),
        })
        req = urllib.request.Request(
            f"{PATHFINDER_URL}?{params}",
            headers={"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req) as resp:
            content = json.load(resp)["data"]["playlistV2"]["content"]
        total = content["totalCount"]
        for item in content["items"]:
            data = (item.get("itemV2") or {}).get("data") or {}
            if data.get("__typename") != "Track" or not data.get("name"):
                continue
            artists = [a["profile"]["name"] for a in data["artists"]["items"]]
            album = data.get("albumOfTrack") or {}
            tracks.append(TrackMeta(
                artist=artists[0] if artists else "",
                title=data["name"],
                album=album.get("name", ""),
                art_url=_largest_image((album.get("coverArt") or {}).get("sources")),
                duration=data["trackDuration"]["totalMilliseconds"] / 1000,
            ))
        offset += 100
    return tracks


def spotify_tracks_noauth(playlist_id, log: Callable[[str], None]) -> list[TrackMeta]:
    state = _embed_state(playlist_id)
    try:
        return _pathfinder_tracks(playlist_id, state["settings"]["session"]["accessToken"])
    except Exception as e:
        log(f"Web-player API failed ({e}) - using embed track list "
            f"(max 100 tracks, no album info).")
        return [TrackMeta(
            artist=t.get("subtitle") or "",
            title=t["title"],
            duration=(t.get("duration") or 0) / 1000,
        ) for t in state["data"]["entity"]["trackList"]]


def spotify_track_noauth(track_id) -> TrackMeta:
    ent = _embed_state(track_id, kind="track")["data"]["entity"]
    images = ent.get("visualIdentity", {}).get("image") or []
    best = max(images, key=lambda im: (im.get("maxWidth") or 0), default=None)
    return TrackMeta(
        artist=ent["artists"][0]["name"] if ent.get("artists") else "",
        title=ent.get("name") or ent.get("title", ""),
        album="",  # not exposed on the embed page for single tracks
        art_url=best["url"] if best else "",
        duration=(ent.get("duration") or 0) / 1000,
    )
