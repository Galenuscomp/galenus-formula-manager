"""E-mail notifications through Resend's HTTP API.

DigitalOcean blocks outgoing SMTP from droplets, so mail goes over HTTPS.
Messages are built inside the request (from committed data) and sent after the
response (FastAPI background tasks): a slow or failing mail service never
blocks or breaks the action itself. Without RESEND_API_KEY nothing is sent.
"""

import logging
from dataclasses import dataclass
from html import escape

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)
API_URL = "https://api.resend.com/emails"


@dataclass
class Message:
    to: str
    subject: str
    html: str
    text: str


def enabled() -> bool:
    return bool(get_settings().resend_api_key)


def link(path: str) -> str:
    return (get_settings().public_origin or "").rstrip("/") + path


def send(message: Message) -> str | None:
    """Send one message; returns None on success, else a short error (also logged)."""
    s = get_settings()
    if not s.resend_api_key:
        return "E-mail is not set up on this server (RESEND_API_KEY)."
    try:
        r = httpx.post(API_URL, timeout=15, headers={"Authorization": f"Bearer {s.resend_api_key}"}, json={
            "from": s.mail_from, "to": [message.to], "subject": message.subject,
            "html": message.html, "text": message.text,
        })
    except httpx.HTTPError as exc:
        log.warning("mail to %s failed: %s", message.to, exc)
        return "Could not reach the e-mail service."
    if r.status_code >= 300:
        try:
            detail = r.json().get("message") or r.text
        except ValueError:
            detail = r.text
        log.warning("mail to %s rejected (%s): %s", message.to, r.status_code, detail[:300])
        return f"The e-mail service refused it ({r.status_code}): {detail[:200]}"
    return None


def deliver(messages: list[Message]) -> None:
    """Background task: send each message; failures are logged, never raised."""
    for m in messages:
        send(m)


# ------------------------------------------------------------------ templates

def _page(title: str, paragraphs: list[str], button: tuple[str, str] | None = None, note: str = "") -> str:
    body = "".join(f'<p style="margin:0 0 14px">{p}</p>' for p in paragraphs)
    if button:
        body += (f'<p style="margin:22px 0"><a href="{escape(button[1])}" style="background:#0d9488;color:#fff;'
                 f'padding:11px 20px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block">'
                 f'{escape(button[0])}</a></p>'
                 f'<p style="margin:0 0 14px;font-size:12px;color:#64748b" dir="ltr">{escape(button[1])}</p>')
    if note:
        body += f'<p style="margin:18px 0 0;font-size:12px;color:#64748b">{note}</p>'
    return (f'<!doctype html><html dir="rtl" lang="he"><body style="margin:0;background:#f1f5f9;'
            f'font-family:Arial,Helvetica,sans-serif;color:#1e293b">'
            f'<div style="max-width:560px;margin:24px auto;background:#fff;border-radius:12px;padding:28px;'
            f'border:1px solid #e2e8f0;line-height:1.55;font-size:15px;text-align:right">'
            f'<p style="margin:0 0 4px;color:#0d9488;font-weight:700">Master Formula Manager</p>'
            f'<h1 style="font-size:19px;margin:0 0 18px">{escape(title)}</h1>{body}</div></body></html>')


def _text(title: str, lines: list[str], url: str = "") -> str:
    return "\n\n".join([title, *lines, url, "Master Formula Manager"]).strip()


def invitation(email: str, name: str, url: str) -> Message:
    title = "הוזמנת למערכת ניהול המאסטר פורמולות"
    lines = [f"שלום {escape(name)},", "נפתח עבורך משתמש במערכת. כדי להתחיל, בחר/י סיסמה בקישור הבא.",
             f"שם המשתמש שלך הוא כתובת המייל: <span dir=\"ltr\">{escape(email)}</span>"]
    return Message(email, title, _page(title, lines, ("בחירת סיסמה", url), "הקישור תקף ל-3 ימים ולשימוש חד-פעמי."),
                   _text(title, [f"שלום {name},", "בחר/י סיסמה בקישור (תקף 3 ימים):"], url))


def password_reset(email: str, name: str, url: str) -> Message:
    title = "איפוס סיסמה"
    lines = [f"שלום {escape(name)},", "התקבלה בקשה לאיפוס הסיסמה שלך. לבחירת סיסמה חדשה:"]
    note = "הקישור תקף ל-24 שעות ולשימוש חד-פעמי. אם לא ביקשת איפוס, אפשר להתעלם מהמייל; הסיסמה הנוכחית לא משתנה."
    return Message(email, title, _page(title, lines, ("בחירת סיסמה חדשה", url), note),
                   _text(title, [f"שלום {name},", "לבחירת סיסמה חדשה (תקף 24 שעות):"], url))


def password_changed(email: str, name: str) -> Message:
    title = "הסיסמה שלך שונתה"
    lines = [f"שלום {escape(name)},", "הסיסמה לחשבון שלך במערכת שונתה זה עתה, וכל החיבורים הפעילים נותקו.",
             "אם לא את/ה שינית אותה, פנה/י מיד למנהל המערכת."]
    return Message(email, title, _page(title, lines), _text(title, lines[1:]))


def awaiting_approval(email: str, name: str, formula: str, number: str, submitter: str, url: str) -> Message:
    title = f"ממתין לאישורך: {formula}"
    lines = [f"שלום {escape(name)},",
             f"{escape(submitter)} הגיש/ה לאישור רוקח את המאסטר פורמולה "
             f"<b dir=\"ltr\">{escape(formula)}</b> (<span dir=\"ltr\">{escape(number)}</span>)."]
    return Message(email, title, _page(title, lines, ("פתיחת הטיוטה", url)),
                   _text(title, [f"{submitter} הגיש/ה לאישור: {formula} ({number})"], url))


DECISION_TITLES = {"approved": "המאסטר פורמולה אושרה", "returned": "הטיוטה הוחזרה לתיקון", "rejected": "הטיוטה נדחתה"}


def decision(email: str, name: str, kind: str, formula: str, number: str, pharmacist: str, notes: str,
             url: str) -> Message:
    title = f"{DECISION_TITLES[kind]}: {formula}"
    lines = [f"שלום {escape(name)},",
             f"{escape(pharmacist)} החליט/ה על <b dir=\"ltr\">{escape(formula)}</b> "
             f"(<span dir=\"ltr\">{escape(number)}</span>): <b>{DECISION_TITLES[kind]}</b>."]
    if notes.strip():
        lines.append("הערת הרוקח: " + escape(notes).replace("\n", "<br>"))
    return Message(email, title, _page(title, lines, ("פתיחת הטיוטה", url)),
                   _text(title, [f"{pharmacist}: {DECISION_TITLES[kind]}", notes], url))


def test_message(email: str) -> Message:
    title = "בדיקת חיבור למייל"
    lines = ["אם קיבלת את המייל הזה, שליחת המיילים מהמערכת עובדת."]
    return Message(email, title, _page(title, lines), _text(title, lines))
