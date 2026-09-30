"""MEDISCA adapter: signs in to medisca.com with the pharmacy's account in a
headless browser and downloads a formula PDF from the formula library.

How the site works (checked against the live site):
- sign-in is a form at /login (email, password); /api/auth/session shows the
  signed-in user;
- the library filtered to one formula number (/formulas/library?q=F000473)
  shows the formula with a button labelled with its number; clicking it posts
  to app.medisca.com/api/medisca/v1/formula_downloads with MEDISCA's internal
  id, and the PDF follows. Without library access (a MEDISCA formulation
  package) that call answers "formula_access_unauthorized".
We click the button like a user rather than calling the API, so we never need
MEDISCA's internal ids. Without a catalog formula number, the library is
searched and only a formula with every requested ingredient and strength is
taken (see best_match); otherwise nothing is downloaded.
"""

import re
import time

from app.catalog import STRENGTH
from app.search import browser
from app.search.automation import Credentials, FoundDocument, SearchFailed, SearchNoResults

SOURCE = "MEDISCA"
BASE_URL = "https://www.medisca.com"
LOGIN_URL = f"{BASE_URL}/login"
SESSION_URL = f"{BASE_URL}/api/auth/session"
LIBRARY_URL = f"{BASE_URL}/formulas/library?q={{}}"
NAV_TIMEOUT_MS = 45_000
FORMULA_NUMBER = re.compile(r"[A-Z]\d{6}")


def _reject_cookies(page) -> None:
    """Choose "Reject All" on the cookie banner (only essential cookies); it blocks clicks."""
    button = page.locator("#onetrust-reject-all-handler")
    try:
        button.wait_for(state="visible", timeout=6000)
        button.click()
        page.wait_for_timeout(500)
    except Exception:
        pass


def _signed_in(context) -> bool:
    try:
        data = context.request.get(SESSION_URL, timeout=20_000).json()
    except Exception:
        return False
    return bool(isinstance(data, dict) and data.get("user"))


def _sign_in(page, context, creds: Credentials) -> None:
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    _reject_cookies(page)
    form = page.locator('form:has(input[name="email"]):has(input[type="password"])').first
    if form.count() == 0:
        raise SearchFailed("MEDISCA sign-in form was not found", retryable=True)
    form.locator('input[name="email"]').fill(creds.username)
    form.locator('input[type="password"]').fill(creds.password)
    form.locator('button[type="submit"]').first.click()
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        page.wait_for_timeout(1000)
        if _signed_in(context):
            browser.save_session(context, creds.key)
            return
    browser.forget_session(creds.key)
    message = browser.page_text(page, 300)
    raise SearchFailed("MEDISCA did not accept the email or password. Check them under Account > Source accounts."
                       + (f" (MEDISCA says: {message[:160]})" if "invalid" in message.lower() else ""),
                       retryable=False)


def _ensure_signed_in(page, context, creds: Credentials) -> None:
    if not _signed_in(context):
        _sign_in(page, context, creds)


def check_login(creds: Credentials) -> None:
    try:
        with browser.exclusive(creds.key, wait=False), browser.browser_context(creds.key) as context:
            page = context.new_page()
            _ensure_signed_in(page, context, creds)
    except SearchFailed:
        raise
    except Exception as exc:
        raise SearchFailed(f"Could not reach MEDISCA: {str(exc).splitlines()[0][:200]}", retryable=True) from exc


def _urls_in(data) -> list[str]:
    """Links anywhere in the download API's JSON answer."""
    if isinstance(data, str):
        return [data] if data.startswith("https://") else []
    if isinstance(data, dict):
        return [u for v in data.values() for u in _urls_in(v)]
    if isinstance(data, list):
        return [u for v in data for u in _urls_in(v)]
    return []


def _pdf_from(context, url: str) -> bytes | None:
    try:
        body = context.request.get(url, timeout=NAV_TIMEOUT_MS).body()
    except Exception:
        return None
    return body if body.startswith(b"%PDF") else None


def _download(page, context, number: str) -> tuple[bytes, str]:
    """Click the formula's button in the library and collect the PDF, however the site delivers it:
    a browser download, a new tab, or a link in the download API's answer."""
    page.goto(LIBRARY_URL.format(number), wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
    _reject_cookies(page)
    button = page.locator("button", has_text=re.compile(rf"^\s*{number}\s*$")).first
    if button.count() == 0:
        raise SearchNoResults()
    row = page.locator("tr", has=button).first
    title = re.sub(r"\s+", " ", row.locator("td").first.inner_text()).strip() if row.count() else ""

    downloads, pages = [], []

    def on_download(d):  # Playwright needs a Python function here, not a bound builtin
        downloads.append(d)

    def on_page(p):
        pages.append(p)
        p.on("download", on_download)

    page.on("download", on_download)
    context.on("page", on_page)
    with page.expect_response(lambda r: "formula_downloads" in r.url, timeout=NAV_TIMEOUT_MS) as info:
        button.click()
    response = info.value
    try:
        answer = response.json()
    except Exception:
        answer = {}
    error = str(answer.get("error", "")) if isinstance(answer, dict) else ""
    if response.status == 401:
        raise SearchFailed("MEDISCA signed us out; retrying", retryable=True)
    if "unauthorized" in error or response.status == 403:
        raise SearchFailed("This MEDISCA account has no access to the formula library (a MEDISCA formulation "
                           "package is required to download formulas).", retryable=False)
    if response.status >= 400:
        raise SearchFailed(f"MEDISCA refused the download ({response.status} {error})".strip(), retryable=False)

    for url in _urls_in(answer):
        pdf = _pdf_from(context, url)
        if pdf:
            return pdf, title
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        for d in downloads:
            path = d.path()
            if path:
                data = open(path, "rb").read()
                if data.startswith(b"%PDF"):
                    return data, title
        for p in pages:
            pdf = _pdf_from(context, p.url) if p.url.startswith("https://") else None
            if pdf:
                return pdf, title
        page.wait_for_timeout(1000)
    keys = sorted(answer) if isinstance(answer, dict) else type(answer).__name__
    raise SearchFailed(f"MEDISCA accepted the download but no PDF arrived (answer fields: {keys})", retryable=True)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"(?<=\d)-(?=[a-z%])", " ", text.lower().replace("per ", "/"))).replace(" /", "/")


def _names(active_ingredient: str) -> list[str]:
    return [n.strip() for n in re.split(r",|\band\b|\+", active_ingredient) if n.strip()]


def _strengths(strength: str) -> list[str]:
    return [s.strip() for s in strength.split(",") if s.strip()]


def best_match(rows: list[dict], active_ingredient: str, strength: str, dosage_form: str) -> dict | None:
    """The library row for this request, or None. A formula counts only if it has every requested
    active ingredient and every requested strength: a similar formula with another strength is
    not downloaded silently. Among those, dosage-form words decide; ties keep MEDISCA's order."""
    # The base name only: salts are written differently ("Lidocaine HCl" / "Lidocaine Hydrochloride").
    names = [n.lower().split()[0] for n in _names(active_ingredient)]
    wanted = [_norm(s).replace(" ", "") for s in _strengths(strength)]
    form_words = re.findall(r"[a-z]{3,}", dosage_form.lower())

    def text_of(row: dict) -> str:
        return _norm(" ".join((row["title"], row.get("route", ""), row.get("form", ""))))

    def fits(row: dict) -> bool:
        text = text_of(row)
        compact = text.replace(" ", "")
        # "5mg/ml" must not match inside "25mg/ml"
        return all(n in text for n in names) and all(
            re.search(rf"(?<![\d.]){re.escape(s)}", compact) for s in wanted)

    def extra_actives(row: dict) -> int:
        """Strengths beyond those requested = other active ingredients. The package size in
        brackets ("(Suspension, 480 mL)") is not a strength."""
        name = re.sub(r"\([^)]*\)", "", row["title"])
        return max(0, len(STRENGTH.findall(name)) - max(1, len(wanted)))

    candidates = [(i, r) for i, r in enumerate(rows) if fits(r)]
    ranked = sorted(candidates, key=lambda item: (
        extra_actives(item[1]), -sum(w in text_of(item[1]) for w in form_words), item[0]))
    return ranked[0][1] if ranked else None


def _search(page, query: str) -> list[dict]:
    page.goto(LIBRARY_URL.format(query), wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
    _reject_cookies(page)
    rows = []
    for tr in page.locator("tbody tr").all():
        cells = [re.sub(r"\s+", " ", c.inner_text()).strip() for c in tr.locator("td").all()]
        if len(cells) >= 4 and FORMULA_NUMBER.fullmatch(cells[-1]):
            rows.append({"number": cells[-1], "title": cells[0], "route": cells[1], "form": cells[2]})
    return rows


def _find(page, active_ingredient: str, strength: str, dosage_form: str) -> dict | None:
    """MEDISCA's search matches the words as one phrase and shows about 20 rows, so search the
    first ingredient with its strength ("Ketoprofen 20%") first, then the ingredient alone."""
    names, strengths = _names(active_ingredient), _strengths(strength)
    if not names:
        return None
    queries = [f"{names[0]} {strengths[0]}"] if strengths else []
    queries.append(names[0])
    for query in queries:
        match = best_match(_search(page, query), active_ingredient, strength, dosage_form)
        if match:
            return match
    return None


def fetch(creds: Credentials, *, active_ingredient: str, formula_id: str = "", title: str = "",
          strength: str = "", dosage_form: str = "") -> FoundDocument:
    number = formula_id.strip().upper()
    if number and not FORMULA_NUMBER.fullmatch(number):
        raise SearchFailed(f"Invalid MEDISCA formula number: {formula_id}", retryable=False)
    try:
        with browser.exclusive(creds.key, wait=True), browser.browser_context(creds.key) as context:
            page = context.new_page()
            _ensure_signed_in(page, context, creds)
            if not number:
                match = _find(page, active_ingredient, strength, dosage_form)
                if match is None:
                    raise SearchNoResults()
                number, title = match["number"], match["title"]
            pdf, found_title = _download(page, context, number)
            browser.save_session(context, creds.key)
    except (SearchFailed, SearchNoResults):
        raise
    except Exception as exc:  # browser/network errors: worth another try
        raise SearchFailed(f"MEDISCA download failed: {str(exc).splitlines()[0][:200]}", retryable=True) from exc
    name = title.strip() or found_title or f"MEDISCA {number}"
    return FoundDocument(pdf=pdf, filename=f"{number}_{browser.safe_filename(name)}.pdf"[:300], source_name=SOURCE,
                         source_formula_id=number, title=name[:500], url=LIBRARY_URL.format(number))
