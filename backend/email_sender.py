"""Outgoing email, provider-agnostic (v3 W7-A M2, 2026-10-18).

The provider is not chosen yet. Two backends, picked from the environment at
send time, so switching providers is a configuration change and no code change:

  console (default)  Nothing leaves the machine. In development the whole
                     message is written to the log (so a developer can click
                     the verification / reset link); with ENV=production only
                     the recipient's domain and the subject are logged — never
                     the body, which carries a one-time link.
  smtp               Any SMTP relay (a transactional provider, the mailbox
                     host, a local relay). Chosen when SMTP_HOST and SMTP_FROM
                     are set. SMTP_PORT (default 587 = STARTTLS; 465 = TLS from
                     the first byte), SMTP_USER / SMTP_PASSWORD (optional),
                     SMTP_TIMEOUT_S (default 10). Up to 3 attempts with a short
                     back-off (CLAUDE.md: every external call retries, max 3).

`send_email` never raises: a failure is logged and returned as False, so a
registration or a reset request never fails because mail is down — the person
can ask for the link again.

Tests use the console backend and read `outbox()` (the last messages sent in
this process, bounded).
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
import time
from collections import deque
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

log = logging.getLogger("pathon.email")

_OUTBOX: deque = deque(maxlen=50)


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str


def outbox() -> list[Message]:
    """Messages the console backend accepted in this process (newest last)."""
    return list(_OUTBOX)


def clear_outbox() -> None:
    _OUTBOX.clear()


def backend_name() -> str:
    """'smtp' when SMTP_HOST and SMTP_FROM are both set, else 'console'."""
    if (os.environ.get("SMTP_HOST") or "").strip() and (os.environ.get("SMTP_FROM") or "").strip():
        return "smtp"
    return "console"


def is_configured() -> bool:
    """True when mail actually leaves the machine (an SMTP relay is set)."""
    return backend_name() == "smtp"


def _production() -> bool:
    return (os.environ.get("ENV") or "").strip().lower() == "production"


def _send_console(msg: Message) -> bool:
    _OUTBOX.append(msg)
    domain = msg.to.rsplit("@", 1)[-1] if "@" in msg.to else "?"
    if _production():
        log.warning("email NOT sent (no SMTP configured): to=*@%s subject=%r", domain, msg.subject)
    else:
        log.info("email (console backend) to=%s subject=%r\n%s", msg.to, msg.subject, msg.text)
    return True


def _build(msg: Message) -> EmailMessage:
    sender = os.environ["SMTP_FROM"].strip()
    em = EmailMessage()
    em["From"] = formataddr(("Pathon", sender)) if "<" not in sender else sender
    em["To"] = msg.to
    em["Subject"] = msg.subject
    em["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1].strip(">") if "@" in sender else None)
    em.set_content(msg.text)
    return em


def _send_smtp(msg: Message) -> bool:
    host = os.environ["SMTP_HOST"].strip()
    port = int(os.environ.get("SMTP_PORT") or 587)
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = os.environ.get("SMTP_PASSWORD") or ""
    timeout = float(os.environ.get("SMTP_TIMEOUT_S") or 10)
    em = _build(msg)
    ctx = ssl.create_default_context()
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            if port == 465:
                with smtplib.SMTP_SSL(host, port, timeout=timeout, context=ctx) as s:
                    if user:
                        s.login(user, password)
                    s.send_message(em)
            else:
                with smtplib.SMTP(host, port, timeout=timeout) as s:
                    s.starttls(context=ctx)
                    if user:
                        s.login(user, password)
                    s.send_message(em)
            return True
        except (smtplib.SMTPException, OSError) as exc:
            last_exc = exc
            # Authentication and recipient refusals do not get better on retry.
            if isinstance(exc, (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused)):
                break
            if attempt < 3:
                time.sleep(0.5 * attempt)
    log.error("email send failed via SMTP (%s:%s) subject=%r: %r", host, port, msg.subject, last_exc)
    return False


def send_email(to: str, subject: str, text: str) -> bool:
    """Send one plain-text email. Returns whether it was accepted; never raises."""
    msg = Message(to=str(to or "").strip(), subject=subject, text=text)
    if not msg.to or "@" not in msg.to:
        log.warning("email skipped: no recipient")
        return False
    try:
        return _send_smtp(msg) if backend_name() == "smtp" else _send_console(msg)
    except Exception as exc:  # noqa: BLE001 — mail must never break the caller
        log.exception("email send crashed: %r", exc)
        return False
