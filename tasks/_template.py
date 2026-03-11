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
COMMAND = "my_new_task"          # Change me
DESCRIPTION = "Short description shown in /start"  # Change me


# ── Optional: put blocking work in a sync helper and run it in a thread ───────
def _do_work() -> str:
    """
    Put your actual logic here.
    This runs in a thread pool, so blocking calls (file I/O, subprocess, etc.)
    are fine and won't freeze the bot.
    """
    # TODO: implement your task
    return "✅ Task completed successfully."


# ── Required: async entry point called by bot.py ──────────────────────────────
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """
    Called when the user sends /my_new_task.
    Must return a string that will be sent back to the user.
    """
    # For CPU/IO-bound work, offload to thread pool:
    result = await asyncio.get_event_loop().run_in_executor(None, _do_work)
    return result

    # For pure async work, just do it directly:
    # return "Hello from my new task!"
