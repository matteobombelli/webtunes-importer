"""Shared data shapes for the Qt-free core."""

from dataclasses import dataclass


@dataclass
class TrackMeta:
    """One track's metadata, produced identically by every source (Spotify,
    Apple Music, YouTube) so the matching/download pipeline is source-agnostic."""

    artist: str = ""
    title: str = ""
    album: str = ""
    art_url: str = ""
    duration: float = 0.0  # seconds; 0 when unknown

    @property
    def label(self) -> str:
        return f"{self.artist} - {self.title}"
