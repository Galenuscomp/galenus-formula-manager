"""Shared headless-browser plumbing for source adapters: one saved session and one
lock per source, so the worker and a "Test login" never use an account at once."""

import fcntl
import re
from contextlib import contextmanager
from pathlib import Path

from app.config import get_settings
from app.search.automation import SearchFailed


def session_dir() -> Path:
    path = get_settings().data_dir / "sessions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path(source: str) -> Path:
    return session_dir() / f"{source.lower()}-state.json"


@contextmanager
def exclusive(source: str, wait: bool):
    with open(session_dir() / f"{source.lower()}.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError as exc:
            raise SearchFailed(f"A {source} download is running right now. Try again in a minute.",
                               retryable=True) from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def browser_context(source: str):
    """A browser context that starts from the source's saved session, if any."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        try:
            state = state_path(source)
            try:
                context = browser.new_context(accept_downloads=True,
                                              storage_state=str(state) if state.exists() else None)
            except Exception:
                state.unlink(missing_ok=True)
                context = browser.new_context(accept_downloads=True)
            yield context
        finally:
            browser.close()


def save_session(context, source: str) -> None:
    context.storage_state(path=str(state_path(source)))


def forget_session(source: str) -> None:
    state_path(source).unlink(missing_ok=True)


def page_text(page, limit: int = 600) -> str:
    try:
        return re.sub(r"\s+", " ", page.locator("body").inner_text()).strip()[:limit]
    except Exception:
        return ""


def safe_filename(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)).strip()[:140]
