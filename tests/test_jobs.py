import webtunes_importer.core.jobs as jobs
from webtunes_importer.core.jobs import JobResult, write_missed_file


def test_write_missed_file_overwrites(monkeypatch, tmp_path):
    target = tmp_path / "last-missed.txt"
    monkeypatch.setattr(jobs, "missed_file_path", lambda: target)

    path = write_missed_file("https://src/1", ["A - B (no match)", "C - D (low bitrate)"])
    text = path.read_text(encoding="utf-8")
    assert "A - B (no match)" in text
    assert "https://src/1" in text

    write_missed_file("https://src/2", [])
    text = target.read_text(encoding="utf-8")
    assert "A - B" not in text  # fully overwritten
    assert "(none - every track was imported)" in text


def test_job_result_summary():
    r = JobResult(total=10, imported=7, missed=["a", "b"], duplicates=["c"])
    assert r.summary == "Done: 7 imported, 2 missed, 1 already in WebTunes (of 10)."
    r.cancelled = True
    assert r.summary.startswith("Cancelled:")
