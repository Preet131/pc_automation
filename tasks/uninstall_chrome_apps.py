"""
tasks/uninstall_chrome_apps.py — Remove Chrome PWA / Web App shortcuts.

Registered bot command : /uninstall_chrome_apps
Trigger from phone     : /uninstall_chrome_apps

What it does:
  1. Scans Chrome's "Web Applications" internal data folder and removes
     sub-directories that match the target app names.
  2. Deletes matching .lnk shortcut files from the Windows Start Menu
     "Chrome Apps" folder so the apps no longer appear in the Start Menu.
  3. Optionally, removes Desktop shortcuts with matching names.

Targets (case-insensitive substring match):
  instagram, snapchat — extend TARGET_APP_NAMES to add more.
"""

import asyncio
import logging
import os
import glob
import shutil

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import CHROME_WEB_APPS_DIR, CHROME_APPS_SHORTCUT_DIR

logger = logging.getLogger(__name__)

# ── Bot command metadata (read by bot.py) ──────────────────────────────────────
COMMAND = "uninstall_chrome_apps"
DESCRIPTION = "Uninstall Chrome web apps (Instagram, Snapchat, …)"

# ── Apps to remove — add more names here as needed ────────────────────────────
TARGET_APP_NAMES: list[str] = [
    "instagram",
    "snapchat",
]


def _matches_target(name: str) -> bool:
    """Return True if the name contains any target app keyword (case-insensitive)."""
    name_lower = name.lower()
    return any(target in name_lower for target in TARGET_APP_NAMES)


def _remove_path(path: str, removed: list, errors: list) -> None:
    """Attempt to remove a file or directory; record the outcome."""
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.isfile(path):
            os.remove(path)
        else:
            return  # Already gone
        removed.append(path)
        logger.info("Removed: %s", path)
    except Exception as exc:
        errors.append(f"{path}: {exc}")
        logger.error("Failed to remove %s — %s", path, exc)


async def run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Main handler called by bot.py when the user sends /uninstall_chrome_apps.
    Runs the blocking filesystem work in a thread pool to avoid blocking the
    asyncio event loop.
    """
    return await asyncio.get_event_loop().run_in_executor(None, _do_uninstall)


def _do_uninstall() -> str:
    """Synchronous worker — safe to run in a thread."""
    removed: list[str] = []
    errors: list[str] = []

    # ── 1. Chrome internal Web Applications data folder ────────────────────────
    if os.path.isdir(CHROME_WEB_APPS_DIR):
        for entry in os.listdir(CHROME_WEB_APPS_DIR):
            if _matches_target(entry):
                _remove_path(os.path.join(CHROME_WEB_APPS_DIR, entry), removed, errors)
    else:
        logger.warning("Chrome Web Apps dir not found: %s", CHROME_WEB_APPS_DIR)

    # ── 2. Start Menu shortcuts ────────────────────────────────────────────────
    if os.path.isdir(CHROME_APPS_SHORTCUT_DIR):
        for lnk in glob.glob(os.path.join(CHROME_APPS_SHORTCUT_DIR, "*.lnk")):
            if _matches_target(os.path.basename(lnk)):
                _remove_path(lnk, removed, errors)

    # ── 3. Desktop shortcuts ───────────────────────────────────────────────────
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.isdir(desktop):
        for lnk in glob.glob(os.path.join(desktop, "*.lnk")):
            if _matches_target(os.path.basename(lnk)):
                _remove_path(lnk, removed, errors)

    # ── Build reply ────────────────────────────────────────────────────────────
    lines = []
    if removed:
        lines.append(f"🗑️ Removed {len(removed)} item(s):")
        lines.extend(f"  • `{os.path.basename(p)}`" for p in removed)
    else:
        lines.append("ℹ️ No matching Chrome web apps found to remove.")

    if errors:
        lines.append(f"\n⚠️ {len(errors)} error(s):")
        lines.extend(f"  • {e}" for e in errors)

    return "\n".join(lines)
