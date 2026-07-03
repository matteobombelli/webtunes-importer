import pytest

from webtunes_importer.constants import DEFAULT_SERVER_URL
from webtunes_importer.core.apple_music import _am_parse
from webtunes_importer.core.jobs import classify_url
from webtunes_importer.core.webtunes import normalize_server_url


def test_am_parse_song_query_param():
    kind, sf, item_id = _am_parse("https://music.apple.com/us/album/some-album/123?i=456")
    assert (kind, sf, item_id) == ("song", "us", "456")


def test_am_parse_playlist():
    kind, sf, item_id = _am_parse(
        "https://music.apple.com/gb/playlist/my-mix/pl.abc123DEF")
    assert (kind, sf, item_id) == ("playlist", "gb", "pl.abc123DEF")


def test_am_parse_album():
    kind, sf, item_id = _am_parse("https://music.apple.com/us/album/great-album/789")
    assert (kind, sf, item_id) == ("album", "us", "789")


def test_am_parse_song_path():
    kind, sf, item_id = _am_parse("https://music.apple.com/us/song/321")
    assert (kind, sf, item_id) == ("song", "us", "321")


def test_am_parse_default_storefront():
    kind, sf, item_id = _am_parse("https://music.apple.com/album/x/42")
    assert sf == "us"


def test_am_parse_rejects_garbage():
    with pytest.raises(RuntimeError):
        _am_parse("https://music.apple.com/us/artist/someone/1")


def test_classify_url():
    assert classify_url("https://open.spotify.com/playlist/37i9dQZF1DX0") == "spotify"
    assert classify_url("https://open.spotify.com/track/4uLU6hMC?si=x") == "spotify"
    assert classify_url("https://music.apple.com/us/album/a/1?i=2") == "apple"
    assert classify_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert classify_url("https://youtu.be/dQw4w9WgXcQ") == "youtube"
    assert classify_url("https://example.com/nope") is None
    assert classify_url("https://open.spotify.com/artist/xyz") is None


def test_normalize_server_url():
    assert normalize_server_url("  https://x.dev/webtunes///  ").rstrip("/") == \
        "https://x.dev/webtunes"
    assert normalize_server_url("https://x.dev/webtunes/") == "https://x.dev/webtunes"
    assert normalize_server_url("") == DEFAULT_SERVER_URL
    assert normalize_server_url(None) == DEFAULT_SERVER_URL
