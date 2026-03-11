"""
tasks/clear_chrome_history.py — Delete Chrome browsing history, cache & downloads list.

Registered bot command : /clear_chrome_history

What it does:
  Removes the following SQLite databases and cache folders from every Chrome
  profile directory found under the User Data folder:
    • History          — visited URLs and page titles
    • History-journal  — SQLite write-ahead log
    • Visited Links    — the bloom-filter that turns links purple
    • Top Sites        — most-visited thumbnails on the New Tab page
    • Thumbnails       — cached page screenshots
    • Cache/           — network cache folder
    • Code Cache/      — JavaScript V8 bytecode cache

Chrome must be closed before running this task; open files cannot be deleted.
"""

import asyncio
import logging
import os
import shutil
import subprocess
import time

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import CHROME_USER_DATA_DIR

logger = logging.getLogger(__name__)

# ── Bot command metadata ───────────────────────────────────────────────────────
COMMAND = "clear_chrome_history"
DESCRIPTION = "Delete all Chrome browsing history, cache, and visited links"

# Files/folders inside each profile dir that store history-related data
HISTORY_TARGETS: list[str] = [
    "History",
    "History-journal",
    "Visited Links",
    "Top Sites",
    "Top Sites-journal",
    "Thumbnails",
    "Cache",
    "Code Cache",
    "GPUCache",
    "Media Cache",
    "Application Cache",
]


def _get_profile_dirs() -> list[str]:
    """
    Return all Chrome profile directories under CHROME_USER_DATA_DIR.
    Chrome creates: Default/, Profile 1/, Profile 2/, …
    """
    if not os.path.isdir(CHROME_USER_DATA_DIR):
        return []

    profiles = []
    for name in os.listdir(CHROME_USER_DATA_DIR):
        full = os.path.join(CHROME_USER_DATA_DIR, name)
        if os.path.isdir(full) and (name == "Default" or name.startswith("Profile ")):
            profiles.append(full)
    return profiles


def _delete_target(path: str, removed: list, errors: list) -> None:
    """Delete a single file or directory tree; record the result."""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            removed.append(f"[dir]  {path}")
            logger.info("Removed dir:  %s", path)
        elif os.path.isfile(path):
            os.remove(path)
            removed.append(f"[file] {path}")
            logger.info("Removed file: %s", path)
    except PermissionError:
        msg = f"{path}: PermissionError — is Chrome open?"
        errors.append(msg)
        logger.warning(msg)
    except Exception as exc:
        msg = f"{path}: {exc}"
        errors.append(msg)
        logger.error("Error deleting %s — %s", path, exc)


def _do_clear() -> str:
    """Synchronous worker that performs the actual deletion."""
    # Force-close Chrome to release OS file locks
    try:
        logger.info("Attempting to force-close Chrome...")
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
        time.sleep(2)  # Give the OS a moment to release file handles
    except Exception as exc:
        logger.warning("Failed to kill Chrome: %s", exc)

    removed: list[str] = []
    errors: list[str] = []

    profiles = _get_profile_dirs()
    if not profiles:
        return f"⚠️ No Chrome profiles found at:\n`{CHROME_USER_DATA_DIR}`"

    for profile in profiles:
        profile_name = os.path.basename(profile)
        logger.info("Processing profile: %s", profile_name)
        for target_name in HISTORY_TARGETS:
            target_path = os.path.join(profile, target_name)
            if os.path.exists(target_path):
                _delete_target(target_path, removed, errors)

    # ── Build reply ────────────────────────────────────────────────────────────
    lines = []
    if removed:
        lines.append(f"🧹 Cleared {len(removed)} history item(s) across {len(profiles)} profile(s).")
    else:
        lines.append("ℹ️ Nothing to clear — history files were already absent.")

    if errors:
        lines.append(f"\n⚠️ {len(errors)} error(s) (Chrome may be open?):")
        lines.extend(f"  • {e}" for e in errors[:5])  # cap at 5 to avoid huge messages
        if len(errors) > 5:
            lines.append(f"  … and {len(errors) - 5} more. See bot.log for details.")

    return "\n".join(lines)


async def run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    return await asyncio.get_event_loop().run_in_executor(None, _do_clear)
