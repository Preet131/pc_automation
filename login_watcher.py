"""
login_watcher.py — Proactive login alert system for the PC Automation Bot.

Sends a Telegram push notification (+ screenshot) to the authorized user
whenever a Windows login event is detected:

  • Type 2  — Interactive login (someone sat down and logged in)
  • Type 7  — Screen unlock (screen was locked and then unlocked)
  • Type 10 — Remote Desktop / network interactive login

Two mechanisms run together:
  1. send_login_alert()   — called once at bot startup for an instant "bot is
                            running = someone just logged in" notification.
  2. watch_login_events() — async background loop; polls the Windows Security
                            Event Log every 10 s for NEW logon events so that
                            unlock / RDP sessions are caught even when the bot
                            was already running.

No extra dependencies — uses PowerShell via subprocess to query the event log.
"""

import asyncio
import io
import logging
import subprocess
from datetime import datetime, timezone

import mss
from PIL import Image

from config.settings import AUTHORIZED_USER_ID

logger = logging.getLogger(__name__)

# ── Logon type descriptions ────────────────────────────────────────────────────
LOGON_TYPE_LABELS = {
    "2":  ("🏠", "Interactive login"),
    "7":  ("🔓", "Screen unlocked"),
    "10": ("🌐", "Remote Desktop login"),
}

# Poll interval (seconds) for the background event watcher
POLL_INTERVAL = 10


# ── Screenshot helper ──────────────────────────────────────────────────────────
def _take_screenshot() -> io.BytesIO:
    """Capture the primary monitor and return a JPEG BytesIO buffer."""
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    buf.seek(0)
    return buf


# ── Windows Event Log query ────────────────────────────────────────────────────
def _query_recent_logons(since_seconds: int = 15) -> list[dict]:
    """
    Query the Windows Security Event Log for interactive logon events
    (Event ID 4624, types 2/7/10) that occurred in the last `since_seconds`.

    Returns a list of dicts: [{"type": "2", "time": "22:05:01"}, ...]
    Uses PowerShell so no third-party libs are needed.
    """
    ps_script = f"""
$cutoff = (Get-Date).AddSeconds(-{since_seconds})
try {{
    $events = Get-WinEvent -FilterHashtable @{{
        LogName   = 'Security'
        Id        = 4624
        StartTime = $cutoff
    }} -ErrorAction SilentlyContinue

    if ($events) {{
        foreach ($e in $events) {{
            $type = $e.Properties[8].Value.ToString()
            if ($type -in @('2','7','10')) {{
                Write-Output "$type|$($e.TimeCreated.ToString('HH:mm:ss'))"
            }}
        }}
    }}
}} catch {{}}
"""
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        events = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if "|" in line:
                logon_type, time_str = line.split("|", 1)
                events.append({"type": logon_type.strip(), "time": time_str.strip()})
        return events
    except Exception as exc:
        logger.warning("Event log query failed: %s", exc)
        return []


# ── Alert sender ───────────────────────────────────────────────────────────────
async def send_login_alert(bot, logon_type: str = "2", event_time: str | None = None):
    """
    Send a push notification + screenshot to AUTHORIZED_USER_ID.

    Args:
        bot:        The telegram.Bot instance.
        logon_type: Windows logon type string ("2", "7", or "10").
        event_time: Time string to display (defaults to now).
    """
    emoji, label = LOGON_TYPE_LABELS.get(logon_type, ("🔔", "Login detected"))
    now = event_time or datetime.now().strftime("%H:%M:%S")
    date = datetime.now().strftime("%Y-%m-%d")

    caption = (
        f"{emoji} *{label} detected!*\n"
        f"🗓 {date}  🕐 {now}\n\n"
        f"_Your PC was just accessed. Here's what the screen looks like right now._"
    )

    try:
        loop = asyncio.get_event_loop()
        buf = await loop.run_in_executor(None, _take_screenshot)
        await bot.send_photo(
            chat_id=AUTHORIZED_USER_ID,
            photo=buf,
            caption=caption,
            parse_mode="Markdown",
        )
        logger.info("Login alert sent — type=%s time=%s", logon_type, now)
    except Exception as exc:
        logger.error("Failed to send login alert: %s", exc, exc_info=True)
        # Fallback: send text-only if photo fails
        try:
            await bot.send_message(
                chat_id=AUTHORIZED_USER_ID,
                text=caption,
                parse_mode="Markdown",
            )
        except Exception:
            pass


# ── Background watcher ─────────────────────────────────────────────────────────
async def watch_login_events(bot):
    """
    Async background loop — polls Windows Event Log every POLL_INTERVAL seconds.
    Sends an alert for each NEW logon event found since the last poll.

    Designed to be launched as an asyncio.Task from bot.py's post_init hook.
    """
    logger.info("Login watcher started (polling every %ds)", POLL_INTERVAL)

    # Skip events that already existed before the watcher started
    # by seeding the seen-set with events from the last 60 s
    seen: set[str] = set()
    for ev in _query_recent_logons(since_seconds=60):
        seen.add(f"{ev['type']}|{ev['time']}")

    while True:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            events = _query_recent_logons(since_seconds=POLL_INTERVAL + 5)
            for ev in events:
                key = f"{ev['type']}|{ev['time']}"
                if key not in seen:
                    seen.add(key)
                    logger.info("New login event detected: type=%s time=%s", ev["type"], ev["time"])
                    await send_login_alert(bot, logon_type=ev["type"], event_time=ev["time"])
        except Exception as exc:
            logger.error("Login watcher loop error: %s", exc, exc_info=True)
