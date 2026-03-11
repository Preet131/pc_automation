"""
tasks/_template.py — Copy this file to create a new automation task.

─────────────────────────────────────────────────────────────────────────────
HOW TO ADD A NEW TASK
─────────────────────────────────────────────────────────────────────────────
1. Copy this file:
       cp tasks/_template.py tasks/my_new_task.py

2. Set COMMAND to the /command you want (no slash, lowercase, underscores ok):
       COMMAND = "my_new_task"

3. Set DESCRIPTION to a short one-line explanation:
       DESCRIPTION = "Does something awesome on my PC"

4. Implement your logic inside run() or in a helper function.

5. Restart the bot.  Your new /my_new_task command is automatically
   discovered and registered — no changes to bot.py required.
─────────────────────────────────────────────────────────────────────────────

EXAMPLE — A task that returns disk usage of the C: drive:

    import shutil
    COMMAND = "disk_usage"
    DESCRIPTION = "Report free space on C: drive"

    async def run(update, context):
        total, used, free = shutil.disk_usage("C:\\\\")
        gb = 1024 ** 3
        return (
            f"💾 C: drive\\n"
            f"  Total : {total/gb:.1f} GB\\n"
            f"  Used  : {used/gb:.1f} GB\\n"
            f"  Free  : {free/gb:.1f} GB"
        )
─────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ── Required metadata — bot.py reads these ────────────────────────────────────
COMMAND = "logout_secret_drive"          # Change me
DESCRIPTION = "Logout from kp150508011@gmail.com"  # Change me


import os
import time
import subprocess

def _do_work() -> str:
    """
    Kills the Google Drive process and resets its user data directory to force a logout.
    """
    # 1. Kill Google Drive FS process
    logger.info("Attempting to kill Google Drive process...")
    try:
        subprocess.run(["taskkill", "/F", "/IM", "GoogleDriveFS.exe", "/T"], capture_output=True)
        time.sleep(3)  # Give the OS a moment to release file handles
    except Exception as exc:
        logger.warning(f"Failed to kill Google Drive: {exc}")

    # 2. Locate DriveFS AppData directory
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    drive_fs_path = os.path.join(local_app_data, "Google", "DriveFS")
    
    if not os.path.exists(drive_fs_path):
        return "⚠️ Google Drive directory not found. Perhaps it is already logged out or not installed?"

    # 3. Rename the directory to force a fresh login state
    backup_path = os.path.join(local_app_data, "Google", f"DriveFS_logout_backup_{int(time.time())}")
    
    try:
        # Renaming acts as a fast wipe that preserves your offline files safely just in case
        os.rename(drive_fs_path, backup_path)
        return (
            "✅ Successfully killed Google Drive and cleared its active session.\n\n"
            "🔒 You are now logged out of all linked accounts (including kp150508011@gmail.com). "
            "Next time you start Google Drive from the Start Menu, it will prompt for a fresh login."
        )
    except PermissionError:
        return "❌ Permission denied. Google Drive files might still be locked by another background service."
    except Exception as exc:
        return f"❌ An error occurred while logging out: {exc}"


# ── Required: async entry point called by bot.py ──────────────────────────────
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Called when the user sends /logout_secret_drive.
    """
    # Offload the blocking work to the thread pool:
    result = await asyncio.get_event_loop().run_in_executor(None, _do_work)
    return result
