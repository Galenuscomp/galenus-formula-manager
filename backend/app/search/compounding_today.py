"""CompoundingToday adapter: logs in with the pharmacy's account in a headless
browser and downloads a formula PDF.

Ported from the earlier formula-automation-worker (Node/Playwright), which
worked against the live site. Browsing and searching compoundingtoday.com are
open to everyone; only the PDF asks to sign in (Login.cfm?DEST=...).
CompoundingToday allows one session per account ("Account in Use"), so:
- the browser session is saved and reused between runs (fewer logins);
- every run holds a file lock, so the worker and a "Test login" never overlap;
- "Account in Use" starts a 5-minute cooldown shared by all processes.
"""

import json
import re
import time
from urllib.parse import urljoin

from app.search import browser
from app.search.automation import Credentials, FoundDocument, SearchCooldown, SearchFailed, SearchNoResults

SOURCE = "CompoundingToday"
BASE_URL = "https://compoundingtoday.com"
FORMULAS_URL = f"{BASE_URL}/formulation/Formula.cfm"
COOLDOWN_SECONDS = 5 * 60
NAV_TIMEOUT_MS = 30_000
LOGIN_FORM = 'form[name="frmLogin2"], form:has(input[name="strPassword"])'


LOGIN_URL = f"{BASE_URL}/Login.cfm"
# CompoundingToday caps PDF downloads per day; its wording is not documented, so match loosely.
_DAILY_LIMIT = re.compile(r"(daily|download)\s+limit|limit\s+(of|has been|reached|exceeded)|exceeded|maximum number", re.I)


def _cooldown_path(key: str):
    return browser.session_dir() / f"{key}-cooldown.json"


def _check_cooldown(key: str) -> None:
    try:
        until = json.loads(_cooldown_path(key).read_text())["until"]
    except (OSError, ValueError, KeyError):
        return
    if until > time.time():
        raise SearchCooldown(f"CompoundingToday account in use; retry in {int(until - time.time())} s")


def _start_cooldown(key: str) -> None:
    _cooldown_path(key).write_text(json.dumps({"until": time.time() + COOLDOWN_SECONDS}))


def _is_login_url(url: str) -> bool:
    return bool(re.search(r"/login\.cfm", url, re.I))


def _account_in_use(page) -> bool:
    return "account in use" in browser.page_text(page).lower()


def _submit_login(page, form, creds: Credentials) -> None:
    form.locator('input[name="strLoginName"], input[type="text"], input[type="email"]').first.fill(creds.username)
    form.locator('input[name="strPassword"], input[type="password"]').first.fill(creds.password)
    submit = form.locator('button[type="submit"], input[type="submit"]').first
    if submit.count() == 0:
        raise SearchFailed("CompoundingToday login button was not found", retryable=False)
    submit.click()
    try:
        page.wait_for_load_state("domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except Exception:
        pass
    page.wait_for_timeout(1000)


def _keyword_search(page, active_ingredient: str) -> list[dict]:
    page.goto(FORMULAS_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    form = page.locator('form[name="frmKeywordSearch"]')
    if form.count() == 0:
        raise SearchFailed("CompoundingToday keyword search form was not found", retryable=True)
    box = form.locator('input[name="searchstr"]')
    box.fill(active_ingredient)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS):
        box.press("Enter")
    page.wait_for_timeout(750)
    found, seen = [], set()
    for link in page.locator('a[href*="FormulaInfo.cfm?ID="]').all():
        href, text = link.get_attribute("href") or "", (link.inner_text() or "").strip()
        m = re.search(r"[?&]ID=(\d+)", href, re.I)
        if m and text and m.group(1) not in seen:
            seen.add(m.group(1))
            found.append({"id": m.group(1), "title": text, "url": f"{BASE_URL}/formulation/FormulaInfo.cfm?ID={m.group(1)}"})
    return found


def _request_pdf(context, pdf_url: str, referer: str) -> bytes | None:
    response = context.request.get(pdf_url, headers={
        "referer": referer, "accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8"}, timeout=NAV_TIMEOUT_MS)
    body = response.body()
    ok = "application/pdf" in (response.headers.get("content-type") or "").lower() and body.startswith(b"%PDF")
    return body if ok and not _is_login_url(response.url) else None


def _download_pdf(page, context, creds: Credentials, pdf_url: str, referer: str) -> bytes:
    """Fetch the PDF with the saved session; if the site sends us to Login.cfm?DEST=..., sign in there."""
    pdf = _request_pdf(context, pdf_url, referer)
    if pdf:
        return pdf
    try:
        page.goto(pdf_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    except Exception:
        pass  # a direct PDF response aborts navigation ("Download is starting")
    _raise_if_blocked(page, creds)
    form = page.locator(LOGIN_FORM).first
    if form.count():
        _submit_login(page, form, creds)
        _raise_if_blocked(page, creds)
    pdf = _request_pdf(context, pdf_url, referer)
    if pdf:
        return pdf
    if _is_login_url(page.url) or page.locator(LOGIN_FORM).count():
        browser.forget_session(creds.key)
        raise SearchFailed("CompoundingToday did not accept the login. Check the username and password "
                           "under Account > Source accounts, and that the membership is active.", retryable=False)
    _raise_if_blocked(page, creds)
    raise SearchFailed("CompoundingToday did not return a PDF for this formula", retryable=True)


def _raise_if_blocked(page, creds: Credentials) -> None:
    if _account_in_use(page):
        _start_cooldown(creds.key)
        raise SearchCooldown("CompoundingToday: Account in Use")
    text = browser.page_text(page, 2000)
    if _DAILY_LIMIT.search(text) and "%PDF" not in text:
        raise SearchFailed("CompoundingToday's daily download limit for this account is reached. "
                           "Try again tomorrow.", retryable=False)


def check_login(creds: Credentials) -> None:
    """Sign in on Login.cfm only. Downloading a PDF would count against the account's daily
    download limit, so "Test login" never does."""
    _check_cooldown(creds.key)
    try:
        with browser.exclusive(creds.key, wait=False), browser.browser_context(creds.key) as context:
            page = context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            form = page.locator(LOGIN_FORM).first
            if form.count() == 0:
                raise SearchFailed("CompoundingToday sign-in form was not found", retryable=True)
            _submit_login(page, form, creds)
            if _account_in_use(page):
                _start_cooldown(creds.key)
                raise SearchCooldown("CompoundingToday: Account in Use")
            if _is_login_url(page.url) and page.locator(LOGIN_FORM).count():
                browser.forget_session(creds.key)
                raise SearchFailed("CompoundingToday did not accept the username or password.", retryable=False)
            browser.save_session(context, creds.key)
    except (SearchCooldown, SearchFailed):
        raise
    except Exception as exc:
        raise SearchFailed(f"Could not reach CompoundingToday: {str(exc).splitlines()[0][:200]}",
                           retryable=True) from exc


def fetch(creds: Credentials, *, active_ingredient: str, formula_id: str = "", title: str = "",
          strength: str = "", dosage_form: str = "") -> FoundDocument:
    formula_id = formula_id.strip()
    if formula_id and not formula_id.isdigit():
        raise SearchFailed(f"Invalid CompoundingToday formula ID: {formula_id}", retryable=False)
    _check_cooldown(creds.key)
    try:
        with browser.exclusive(creds.key, wait=True), browser.browser_context(creds.key) as context:
            page = context.new_page()
            if formula_id:
                selected = {"id": formula_id, "title": title.strip(),
                            "url": f"{BASE_URL}/formulation/FormulaInfo.cfm?ID={formula_id}"}
            else:
                results = _keyword_search(page, active_ingredient)
                if not results:
                    raise SearchNoResults()
                selected = results[0]
            page.goto(selected["url"], wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
            if not selected["title"]:
                heading = page.locator("h1, h2, h3").first
                selected["title"] = re.sub(r"\s+", " ", heading.inner_text()).strip()[:300] if heading.count() else ""
            link = page.locator('a[href*="FormulaPDF.cfm?FormulaID="]').first
            if link.count() == 0:
                raise SearchFailed("CompoundingToday formula page has no PDF link", retryable=False)
            pdf_url = urljoin(page.url, link.get_attribute("href") or "")
            pdf = _download_pdf(page, context, creds, pdf_url, selected["url"])
            browser.save_session(context, creds.key)
    except (SearchCooldown, SearchFailed, SearchNoResults):
        raise
    except Exception as exc:  # browser/network errors: worth another try
        raise SearchFailed(f"CompoundingToday download failed: {str(exc).splitlines()[0][:200]}", retryable=True) from exc
    name = selected["title"] or f"CompoundingToday Formula {selected['id']}"
    return FoundDocument(pdf=pdf, filename=f"{selected['id']}_{browser.safe_filename(name)}.pdf"[:300],
                         source_name=SOURCE, source_formula_id=selected["id"], title=name[:500], url=selected["url"])
