"""YouTube catalog search for the Search tab (onthespot's approach): a flat
ytsearchN query - fast because nothing is resolved until the user imports."""

from webtunes_importer.constants import SEARCH_TAB_RESULTS
from webtunes_importer.core.matching import make_ydl
from webtunes_importer.core.queue_model import ImportItem


def _best_thumbnail(entry) -> str | None:
    thumbs = entry.get("thumbnails") or []
    if thumbs:
        best = max(thumbs, key=lambda t: (t.get("width") or 0))
        return best.get("url")
    return entry.get("thumbnail")


def search_youtube(term: str, limit: int = SEARCH_TAB_RESULTS) -> list[ImportItem]:
    with make_ydl(extract_flat=True) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{term}", download=False)
    items = []
    for entry in info.get("entries") or []:
        if not entry:
            continue
        url = entry.get("url") or entry.get("webpage_url")
        if not url:
            continue
        items.append(ImportItem(
            item_id=entry.get("id") or url,
            title=entry.get("title") or "(untitled)",
            by=entry.get("uploader") or entry.get("channel") or "",
            url=url,
            duration=entry.get("duration"),
            thumbnail_url=_best_thumbnail(entry),
        ))
    return items
