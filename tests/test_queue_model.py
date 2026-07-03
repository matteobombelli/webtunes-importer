from webtunes_importer.core.queue_model import ImportItem, ImportQueue, ItemStatus, LinkJob


def _item(item_id="a"):
    return ImportItem(item_id=item_id, title="T", by="B", url="https://yt/x")


def test_fifo_order():
    q = ImportQueue()
    q.put(_item("1"))
    q.put(_item("2"))
    assert q.claim().item_id == "1"
    assert q.claim().item_id == "2"


def test_claim_timeout_returns_none():
    q = ImportQueue()
    assert q.claim(timeout=0.01) is None


def test_cancelled_item_skipped():
    q = ImportQueue()
    first, second = _item("1"), _item("2")
    q.put(first)
    q.put(second)
    q.cancel_item("1")
    claimed = q.claim()
    assert claimed.item_id == "2"
    assert first.status is ItemStatus.CANCELLED


def test_mixed_units():
    q = ImportQueue()
    job = LinkJob(url="https://open.spotify.com/playlist/x")
    q.put(job)
    q.put(_item())
    assert q.claim() is job
    assert isinstance(q.claim(), ImportItem)
    assert q.pending_count() == 0
