"""
tasks/logout_social_media.py — Clear Chrome session cookies for social media sites.

Registered bot command : /logout_social_media

What it does:
  Opens Chrome's "Cookies" SQLite database in each profile and DELETEs all
  rows whose host_key matches social-media domains.  This effectively logs
  Chrome out of those sites without touching any other cookies.

  Target domains (extend SOCIAL_DOMAINS to add more):
    • facebook.com, instagram.com, threads.net
    • snapchat.com
    • twitter.com, x.com
    • tiktok.com
    • reddit.com
    • linkedin.com

  Chrome must NOT be open; Chrome holds an exclusive lock on the Cookies file
  while running.  The task detects this and reports it clearly.
"""

import asyncio
import logging
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import CHROME_USER_DATA_DIR

logger = logging.getLogger(__name__)

# ── Bot command metadata ───────────────────────────────────────────────────────
COMMAND = "logout_social_media"
DESCRIPTION = "Log out of social media in Chrome by clearing session cookies"

# Add/remove domains as you like
SOCIAL_DOMAINS: list[str] = [
    "facebook.com",
    "instagram.com",
    "threads.net",
    "snapchat.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "reddit.com",
    "linkedin.com",
    "pinterest.com",
    "tumblr.com",
]


def _get_cookie_dbs() -> list[str]:
    """Return paths to every Chrome profile's Cookies SQLite file."""
    if not os.path.isdir(CHROME_USER_DATA_DIR):
        return []

    paths = []
    for name in os.listdir(CHROME_USER_DATA_DIR):
        profile_dir = os.path.join(CHROME_USER_DATA_DIR, name)
        if not os.path.isdir(profile_dir):
            continue
        if name != "Default" and not name.startswith("Profile "):
            continue
        # Try new location (Chrome 114+)
        cookie_file_new = os.path.join(profile_dir, "Network", "Cookies")
        # Try old location
        cookie_file_old = os.path.join(profile_dir, "Cookies")
        
        if os.path.isfile(cookie_file_new):
            paths.append(cookie_file_new)
        elif os.path.isfile(cookie_file_old):
            paths.append(cookie_file_old)
            
    return paths


def _clear_cookies_in_db(cookie_db_path: str) -> tuple[int, str | None]:
    """
    Delete social-media cookies from a single Cookies SQLite file.
    Works on a temporary copy to avoid corrupting the original if Chrome
    is open; then replaces the original on success.

    Returns (rows_deleted, error_message_or_None).
    """
    # Work on a temp copy so we never corrupt the live file
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    try:
        shutil.copy2(cookie_db_path, tmp_path)

        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Build WHERE clause: host_key LIKE '%facebook.com' OR …
        conditions = " OR ".join(
            ["host_key LIKE ?"] * len(SOCIAL_DOMAINS)
        )
        params = [f"%{d}" for d in SOCIAL_DOMAINS]

        cursor.execute(f"DELETE FROM cookies WHERE {conditions}", params)
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        # Replace original only if the write succeeded
        shutil.move(tmp_path, cookie_db_path)
        logger.info("Cleared %d cookies from %s", deleted, cookie_db_path)
        return deleted, None

    except sqlite3.OperationalError as exc:
        # Typically "database is locked" when Chrome is open
        err = f"DB locked ({exc}) — is Chrome running?"
        logger.warning("%s: %s", cookie_db_path, err)
        return 0, err
    except Exception as exc:
        logger.error("Error processing %s: %s", cookie_db_path, exc, exc_info=True)
        return 0, str(exc)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _do_logout() -> str:
    """Synchronous worker."""
    # Force close Chrome before operating to release SQLite locks
    try:
        logger.info("Attempting to force-close Chrome...")
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
        time.sleep(2)  # Give the OS a moment to release file handles
    except Exception as exc:
        logger.warning("Failed to kill Chrome: %s", exc)

    cookie_dbs = _get_cookie_dbs()
    if not cookie_dbs:
        return f"⚠️ No Chrome Cookies files found under:\n`{CHROME_USER_DATA_DIR}`"

    total_deleted = 0
    errors: list[str] = []

    for db_path in cookie_dbs:
        profile_name = os.path.basename(os.path.dirname(db_path))
        deleted, err = _clear_cookies_in_db(db_path)
        total_deleted += deleted
        if err:
            errors.append(f"{profile_name}: {err}")

    lines = []
    if total_deleted:
        lines.append(
            f"🔓 Logged out of social media — deleted {total_deleted} cookie(s) "
            f"across {len(cookie_dbs)} Chrome profile(s)."
        )
        lines.append("\nTargeted domains:")
        lines.extend(f"  • {d}" for d in SOCIAL_DOMAINS)
    else:
        lines.append("ℹ️ No social-media cookies found (already logged out?).")

    if errors:
        lines.append(f"\n⚠️ {len(errors)} error(s):")
        lines.extend(f"  • {e}" for e in errors)
        lines.append("\n💡 Make sure Chrome is closed before running this command.")

    return "\n".join(lines)


async def run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    return await asyncio.get_event_loop().run_in_executor(None, _do_logout)
