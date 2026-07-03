"""The single import worker and its signal bridge to the GUI thread.

Downloads run strictly sequentially (a hard-won 429 lesson from the exporter
this app descends from): one daemon thread drains the shared queue, whether
the work came from the Links tab or the Search tab. Workers never touch
widgets - everything crosses to the main thread via queued signal delivery.
"""

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from webtunes_importer.config import Settings
from webtunes_importer.core.jobs import Emit, import_single_video, run_link_job
from webtunes_importer.core.queue_model import ImportItem, ImportQueue, ItemStatus, LinkJob
from webtunes_importer.core.webtunes import AuthRevokedError, WebTunesClient


class WorkerSignals(QObject):
    log = Signal(str)
    job_progress = Signal(int, int)  # done, total
    job_counts = Signal(int, int)  # imported, missed
    job_finished = Signal(object)  # JobResult on success, Exception on failure
    item_update = Signal(str, object, int)  # item_id, ItemStatus, percent
    auth_revoked = Signal()


class ImportWorker(threading.Thread):
    def __init__(
        self,
        queue: ImportQueue,
        signals: WorkerSignals,
        get_settings: Callable[[], Settings],
        get_client: Callable[[], WebTunesClient | None],
    ):
        super().__init__(daemon=True, name="import-worker")
        self.queue = queue
        self.signals = signals
        self.get_settings = get_settings
        self.get_client = get_client
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            unit = self.queue.claim(timeout=0.5)
            if unit is None:
                continue
            client = self.get_client()
            if client is None:
                # connection dropped while the item sat in the queue
                if isinstance(unit, LinkJob):
                    self.signals.job_finished.emit(AuthRevokedError("not connected"))
                else:
                    unit.status = ItemStatus.FAILED
                    unit.error = "not connected"
                    self.signals.item_update.emit(unit.item_id, ItemStatus.FAILED, 0)
                continue
            if isinstance(unit, LinkJob):
                self._run_link_job(unit, client)
            elif isinstance(unit, ImportItem):
                self._run_item(unit, client)

    def _run_link_job(self, job: LinkJob, client: WebTunesClient) -> None:
        emit = Emit(
            log=self.signals.log.emit,
            progress=self.signals.job_progress.emit,
            counts=self.signals.job_counts.emit,
        )
        try:
            result = run_link_job(job.url, self.get_settings(), client, emit, job.cancel)
            self.signals.job_finished.emit(result)
        except AuthRevokedError as e:
            self.signals.auth_revoked.emit()
            self.signals.job_finished.emit(e)
        except Exception as e:
            self.signals.job_finished.emit(e)

    def _run_item(self, item: ImportItem, client: WebTunesClient) -> None:
        try:
            import_single_video(
                item,
                self.get_settings(),
                client,
                update=self.signals.item_update.emit,
                log=self.signals.log.emit,
            )
        except AuthRevokedError:
            self.signals.auth_revoked.emit()
