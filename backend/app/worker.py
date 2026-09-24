"""Background worker: `python -m app.worker`."""

import logging
import signal
import threading
import time

from app import jobs
from app.config import get_settings
from app.db import session_factory

log = logging.getLogger("worker")


def loop(stop: threading.Event) -> None:
    settings = get_settings()
    last_recovery = 0.0
    while not stop.is_set():
        try:
            with session_factory()() as db:
                if time.monotonic() - last_recovery > 30:
                    jobs.recover_expired_leases(db)
                    last_recovery = time.monotonic()
                job = jobs.claim_next(db)
                if job is not None:
                    log.info("running %s job %s", job.kind, job.id)
                    jobs.run_job(db, job)
                    continue
        except Exception:
            log.exception("worker iteration failed")
        stop.wait(settings.worker_poll_seconds)


def start_in_thread() -> threading.Event:
    stop = threading.Event()
    threading.Thread(target=loop, args=(stop,), name="job-worker", daemon=True).start()
    return stop


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    log.info("worker started")
    loop(stop)


if __name__ == "__main__":
    main()
