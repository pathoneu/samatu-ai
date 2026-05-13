"""Send the Week 1 Task 1.1 disclosure email to current beta users.

Usage:
  python scripts/send_beta_disclosure.py --dry-run      # print what would be sent
  python scripts/send_beta_disclosure.py --send         # actually send (requires SMTP env)

Environment for --send:
  BETA_DISCLOSURE_SMTP_HOST       e.g. smtp.gmail.com
  BETA_DISCLOSURE_SMTP_PORT       e.g. 587
  BETA_DISCLOSURE_SMTP_USER
  BETA_DISCLOSURE_SMTP_PASS
  BETA_DISCLOSURE_FROM_ADDRESS    e.g. solutions@pathon.eu
  BETA_DISCLOSURE_USERS_FILE      JSON list of {"email": "...", "name": "..."}

Beta-stage note: the canonical plan (D1) requires this disclosure even though
no payment wall is enabled yet — beta users may still be bidding real EUR.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "backend" / "data" / "email_templates" / "beta_disclosure_lt.md"


def load_template() -> tuple[str, str]:
    """Return (subject, body) split on the first blank line after the Tema line."""
    raw = TEMPLATE.read_text(encoding="utf-8")
    lines = raw.splitlines()
    subject = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.lower().startswith("tema:"):
            subject = line.split(":", 1)[1].strip()
            body_start = i + 1
            break
    # Skip the blank line(s) right after the subject.
    while body_start < len(lines) and not lines[body_start].strip():
        body_start += 1
    body = "\n".join(lines[body_start:])
    return subject, body


def load_beta_users() -> list[dict]:
    """Load beta users from the file referenced by BETA_DISCLOSURE_USERS_FILE.

    File format: JSON array of {email, name}. Returns [] if missing/empty.
    """
    path = os.environ.get("BETA_DISCLOSURE_USERS_FILE")
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"WARNING: failed to parse {p}: {e}", file=sys.stderr)
        return []


def send_via_smtp(to_email: str, subject: str, body: str) -> None:
    host = os.environ["BETA_DISCLOSURE_SMTP_HOST"]
    port = int(os.environ["BETA_DISCLOSURE_SMTP_PORT"])
    user = os.environ["BETA_DISCLOSURE_SMTP_USER"]
    password = os.environ["BETA_DISCLOSURE_SMTP_PASS"]
    from_addr = os.environ["BETA_DISCLOSURE_FROM_ADDRESS"]

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Print template + recipients only")
    group.add_argument("--send", action="store_true", help="Actually send via SMTP")
    args = parser.parse_args()

    subject, body = load_template()
    users = load_beta_users()

    if args.dry_run:
        print("=" * 60)
        print("DRY RUN — would send the following email:")
        print(f"Subject: {subject}")
        print("-" * 60)
        print(body)
        print("=" * 60)
        if not users:
            print("No beta users loaded (set BETA_DISCLOSURE_USERS_FILE to a JSON list).")
        else:
            print(f"Would send to {len(users)} recipient(s):")
            for u in users:
                print(f"  - {u.get('email')} ({u.get('name', '')})")
        return 0

    if not users:
        print("ERROR: no recipients loaded; aborting --send.", file=sys.stderr)
        return 2

    sent = 0
    failed = 0
    for u in users:
        email = u.get("email")
        if not email:
            failed += 1
            continue
        try:
            send_via_smtp(email, subject, body)
            sent += 1
            print(f"sent: {email}")
        except Exception as exc:
            failed += 1
            print(f"failed: {email}: {exc}", file=sys.stderr)
    print(f"Done. sent={sent} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
