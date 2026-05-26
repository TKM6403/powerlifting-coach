#!/usr/bin/env python3
"""
send-program.py — deliver today's (or any day's) training session.

Two modes:
  --mode imessage  (default; macOS only, uses Messages.app)
  --mode email     (cross-platform; SMTP via Gmail; for GitHub Actions cron)

Reads program/this-week.md, extracts the requested day's section, inlines a
brief version of the referenced warmup-library entry, and sends.

Usage:
    python scripts/send-program.py                       # today, iMessage
    python scripts/send-program.py --day Mon             # specific day
    python scripts/send-program.py --dry-run             # print, don't send
    python scripts/send-program.py --mode email          # email instead
    python scripts/send-program.py --phone +1555...      # override phone

Email mode env vars (read from environment, e.g. GitHub Action secrets):
    GMAIL_APP_PASSWORD   required — Gmail app password for the sender
    GMAIL_FROM           optional — sender address (default tarun.marthes@gmail.com)
    GMAIL_TO             optional — recipient (default tarun.marthes@gmail.com)
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import smtplib
import ssl
import subprocess
import sys
import tempfile
from email.message import EmailMessage
from pathlib import Path

PHONE = "+18015606099"
DEFAULT_EMAIL = "tarun.marthes@gmail.com"
REPO = Path(__file__).resolve().parent.parent
WEEK_FILE = REPO / "program" / "this-week.md"
WARMUP_FILE = REPO / "reference" / "warmup-library.md"

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]
DAY_ABBR = {d[:3].lower(): d for d in DAY_NAMES}


def parse_day_sections(week_md: str) -> dict:
    """Return {DayName: section_markdown} for each ## DayName section."""
    sections = {}
    current_day, current_lines = None, []
    for line in week_md.splitlines():
        m = re.match(r"^##\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", line)
        if m:
            if current_day:
                sections[current_day] = "\n".join(current_lines).strip()
            current_day = m.group(1)
            current_lines = [line]
        elif line.startswith("## ") and current_day:
            sections[current_day] = "\n".join(current_lines).strip()
            current_day, current_lines = None, []
        elif current_day is not None:
            current_lines.append(line)
    if current_day:
        sections[current_day] = "\n".join(current_lines).strip()
    return sections


def extract_warmup_ref(section_text: str) -> str | None:
    """Find a 'warmup-library.md → EntryName' reference in the section."""
    m = re.search(r"warmup-library\.md[^→\n]*→\s*([^.\n]+)", section_text)
    return m.group(1).strip() if m else None


def _find_section(lines: list, keywords: list, require_numbered: bool = False) -> int | None:
    """Return line index of the first ## section matching all keywords.

    If require_numbered, only match sections containing a numbered+bold bullet.
    """
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        header = line[3:].lower()
        if not all(k in header for k in keywords):
            continue
        if not require_numbered:
            return i
        # Scan forward to verify a numbered+bold bullet exists before next ##
        for fwd in lines[i + 1:]:
            if fwd.startswith("## "):
                break
            if re.match(r"^\s*\d+\.\s+\*\*", fwd):
                return i
    return None


def get_warmup_bullets(warmup_md: str, entry_name: str, limit: int = 8) -> list[str]:
    """Pull up to `limit` brief move bullets from a warmup-library entry.

    If the matched section is a "Same structure" modifications-only block,
    fall back to the corresponding base section for that lift.
    """
    if not entry_name:
        return []
    lines = warmup_md.splitlines()
    keywords = [w.lower() for w in re.split(r"[(\s/]+", entry_name) if len(w) > 2][:2]
    start = _find_section(lines, keywords, require_numbered=False)
    if start is None:
        return []
    # If this section is modifications-only ("Same structure..."), prefer the base section
    section_preview = "\n".join(lines[start + 1: start + 4]).lower()
    if "same structure" in section_preview or section_preview.lstrip().startswith("same "):
        base = _find_section(lines, keywords[:1], require_numbered=True)
        if base is not None and base != start:
            start = base
    bullets = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        # Try: numbered with bold name -> "1. **Move** — detail"
        m = re.match(r"^\s*\d+\.\s+\*\*(.+?)\*\*\s*[—-]\s*(.+)$", line)
        if m:
            move, detail = m.group(1), m.group(2)
        else:
            # Fall back: numbered plain -> "1. Move — detail" or "1. Move"
            m = re.match(r"^\s*\d+\.\s+(.+?)(?:\s*[—-]\s*(.+))?$", line)
            if m:
                move = m.group(1).replace("**", "").strip()
                detail = (m.group(2) or "").replace("**", "").strip()
            else:
                # Fall back: dash bullet (modification lists)
                m = re.match(r"^\s*-\s+(.+)$", line)
                if not m:
                    continue
                content = m.group(1).replace("**", "").strip()
                # Trim and add as one-liner
                if len(content) > 60:
                    content = content[:57].rsplit(" ", 1)[0] + "…"
                bullets.append(f"• {content}")
                if len(bullets) >= limit:
                    break
                continue
        if len(detail) > 55:
            detail = detail[:52].rsplit(" ", 1)[0] + "…"
        bullets.append(f"• {move} — {detail}" if detail else f"• {move}")
        if len(bullets) >= limit:
            break
    return bullets


def format_session(day_name: str, section: str, warmup_bullets: list[str]) -> str:
    """Render the section into a clean plain-text iMessage body."""
    out = []
    for raw in section.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("## "):
            header = stripped[3:].replace("**", "")
            header = re.sub(r"\s*\*[^*]+\*\s*$", "", header).strip()
            out.append(header.upper())
            out.append("")
            continue

        if stripped.startswith("**Warmup:**"):
            if warmup_bullets:
                out.append("WARMUP (brief):")
                out.extend(warmup_bullets)
                out.append("")
            continue

        if stripped.startswith("**Cooldown:**"):
            out.append(stripped.replace("**", ""))
            continue

        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # Skip separator and header rows
            if all(re.fullmatch(r"-+", c or "-") for c in cells):
                continue
            if cells[:1] == ["Exercise"]:
                if "WORKING SETS" not in out[-3:]:
                    out.append("")
                    out.append("WORKING SETS:")
                continue
            if len(cells) >= 4:
                cells = [c.replace("**", "") for c in cells]
                exercise, sets_, reps_, rpe_load = cells[0], cells[1], cells[2], cells[3]
                notes = cells[4] if len(cells) > 4 else ""
                bullet = f"• {exercise}: {sets_}×{reps_} @ {rpe_load}"
                if notes:
                    bullet += f" — {notes}"
                out.append(bullet)
            continue

        # Plain content — strip bold/italic markers
        out.append(stripped.replace("**", ""))
    return "\n".join(out)


def extract_subject(section: str, day_name: str) -> str:
    """Pull a short subject line from the section's ## header."""
    for line in section.splitlines():
        if line.startswith("## "):
            header = line[3:].replace("**", "").strip()
            # Strip italic time annotation: "## Mon 5/25 — Squat Primary  *(~75 min)*"
            header = re.sub(r"\s*\*[^*]+\*\s*$", "", header).strip()
            # Compact: "Monday 5/25 — Squat Primary" -> "Mon 5/25 — Squat Primary"
            return header.replace(day_name, day_name[:3], 1)
    return f"{day_name[:3]} — training"


def send_email(to_addr: str, from_addr: str, subject: str,
               body: str, app_password: str) -> None:
    """Send via Gmail SMTP."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465,
                          context=ssl.create_default_context()) as s:
        s.login(from_addr, app_password)
        s.send_message(msg)


def send_imessage(phone: str, message: str) -> None:
    """Send via Messages.app. Uses a tempfile to avoid AppleScript escaping pain."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                     delete=False, encoding="utf-8") as f:
        f.write(message)
        tmp = f.name
    script = f'''
    set msgContent to read POSIX file "{tmp}" as «class utf8»
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddy to buddy "{phone}" of targetService
        send msgContent to targetBuddy
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script],
                            capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if result.returncode != 0:
        sys.stderr.write(f"iMessage send failed:\n{result.stderr}\n")
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--mode", choices=["imessage", "email"], default="imessage",
                    help="Delivery mode (default: imessage)")
    ap.add_argument("--day", help="Day (Mon/Tue/.../Monday/Tuesday). Default = today.")
    ap.add_argument("--phone", default=PHONE, help=f"iMessage recipient (default {PHONE})")
    ap.add_argument("--dry-run", action="store_true", help="Print, don't send")
    args = ap.parse_args()

    if args.day:
        day_name = DAY_ABBR.get(args.day.lower()[:3])
        if not day_name:
            sys.exit(f"Unknown day: {args.day}")
    else:
        day_name = DAY_NAMES[datetime.date.today().weekday()]

    week_md = WEEK_FILE.read_text(encoding="utf-8")
    warmup_md = WARMUP_FILE.read_text(encoding="utf-8")

    sections = parse_day_sections(week_md)
    section = sections.get(day_name)
    if not section:
        sys.exit(f"No section for {day_name} in this-week.md")

    warmup_entry = extract_warmup_ref(section)
    warmup_bullets = get_warmup_bullets(warmup_md, warmup_entry) if warmup_entry else []
    message = format_session(day_name, section, warmup_bullets)

    if args.dry_run:
        if args.mode == "email":
            print(f"Subject: {extract_subject(section, day_name)}\n")
        print(message)
        return

    if args.mode == "email":
        app_pw = os.environ.get("GMAIL_APP_PASSWORD")
        if not app_pw:
            sys.exit("GMAIL_APP_PASSWORD not set in environment")
        from_addr = os.environ.get("GMAIL_FROM", DEFAULT_EMAIL)
        to_addr = os.environ.get("GMAIL_TO", DEFAULT_EMAIL)
        subject = extract_subject(section, day_name)
        send_email(to_addr, from_addr, subject, message, app_pw)
        print(f"Emailed {day_name} session to {to_addr}")
    else:
        send_imessage(args.phone, message)
        print(f"Sent {day_name} session to {args.phone}")


if __name__ == "__main__":
    main()
