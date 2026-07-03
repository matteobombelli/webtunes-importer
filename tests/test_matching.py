import pytest

from webtunes_importer.core.matching import (
    _ratio,
    best_audio_kbps,
    find_match,
    match_score,
    normalize,
    version_allowed,
)
from webtunes_importer.core.models import TrackMeta


class FakeYdl:
    def __init__(self, info):
        self.info = info
        self.queries = []

    def extract_info(self, query, download=False):
        self.queries.append(query)
        return self.info


def test_normalize_strips_brackets_and_noise():
    assert normalize("Song Title (Official Video) [HD]") == "song title"
    assert normalize("Artist - Song (Lyrics)") == "artist song"


def test_version_allowed_studio_rejects_live_and_junk():
    assert not version_allowed("Song (Live at Wembley)", "studio")
    assert not version_allowed("Song - sped up nightcore", "studio")
    assert version_allowed("Song (Official Video)", "studio")
    # documented caveat: word-boundary matching mis-flags legitimate titles
    assert not version_allowed("Live and Let Die", "studio")


def test_version_allowed_live_requires_live_marker():
    assert version_allowed("Song live in Paris", "live")
    assert not version_allowed("Song (Official Video)", "live")


def test_version_allowed_none_allows_everything():
    assert version_allowed("Song (Live) remix karaoke", "none")


def test_ratio_is_word_order_invariant():
    assert _ratio("artist title", "title artist") == 1.0


def test_match_score_prefers_exact_title():
    track = TrackMeta(artist="Foo", title="Bar", duration=200)
    exact = {"title": "Foo - Bar (Official Video)", "duration": 200}
    other = {"title": "Completely Different Song", "duration": 200}
    assert match_score(track, exact) > match_score(track, other)


def test_match_score_uses_channel_for_topic_uploads():
    track = TrackMeta(artist="Foo", title="Bar", duration=200)
    topic = {"title": "Bar", "uploader": "Foo - Topic", "duration": 200}
    bare = {"title": "Bar", "duration": 200}
    assert match_score(track, topic) > match_score(track, bare)


def test_match_score_duration_penalty():
    track = TrackMeta(artist="Foo", title="Bar", duration=200)
    close = {"title": "Foo Bar", "duration": 205}
    far = {"title": "Foo Bar", "duration": 400}
    assert match_score(track, close) - match_score(track, far) == pytest.approx(0.2)


def test_find_match_returns_best_above_threshold():
    track = TrackMeta(artist="Foo", title="Bar", duration=200)
    ydl = FakeYdl({"entries": [
        {"title": "Foo - Bar", "url": "https://yt/1", "duration": 200},
        {"title": "Unrelated", "url": "https://yt/2", "duration": 200},
    ]})
    url, score, reason = find_match(track, ydl, "none", threshold=0.7)
    assert url == "https://yt/1"
    assert reason is None
    assert score >= 0.7


def test_find_match_below_threshold_gives_reason():
    track = TrackMeta(artist="Foo", title="Bar", duration=200)
    ydl = FakeYdl({"entries": [{"title": "zzz", "url": "https://yt/1", "duration": 999}]})
    url, score, reason = find_match(track, ydl, "none", threshold=0.9)
    assert url is None
    assert "below strictness" in reason


def test_find_match_no_candidates_for_preference():
    track = TrackMeta(artist="Foo", title="Bar")
    ydl = FakeYdl({"entries": [{"title": "Foo - Bar (studio)", "url": "u"}]})
    url, score, reason = find_match(track, ydl, "live", threshold=0.1)
    assert url is None
    assert "no live version" in reason
    assert ydl.queries[0].endswith("Foo Bar live")


def test_best_audio_kbps_picks_max_audio_rate():
    ydl = FakeYdl({"formats": [
        {"acodec": "opus", "abr": 128},
        {"acodec": "none", "tbr": 9999},
        {"acodec": "mp4a", "tbr": 64},
    ]})
    assert best_audio_kbps("u", ydl) == 128


def test_best_audio_kbps_empty_is_zero():
    assert best_audio_kbps("u", FakeYdl({"formats": []})) == 0
