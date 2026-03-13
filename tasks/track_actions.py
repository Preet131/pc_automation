"""
tasks/track_actions.py — Monitor the active window and stream changes live to Telegram.

Registered bot command : /track_actions

What it does:
  Monitors the currently focused window on the PC every second.
  If the active window title changes (e.g., user switches from a browser 
  to File Explorer), it immediately sends a new Telegram message to the user.
  Runs for a specified duration (default 10 minutes).
"""

import asyncio
import ctypes
import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

COMMAND = "track_actions"
DESCRIPTION = "Track active windows/apps live for up to 10 minutes"

# Global state to prevent multiple trackers running at once
_TRACKER_TASK = None


def get_active_window_title() -> str:
    """Use ctypes to get the title of the currently focused window on Windows."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return ""
    
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value.strip()


async def _run_tracker(chat_id: int, bot, duration_minutes: float):
    """Background loop that polls the active window and sends text messages on changes."""
    logger.info("Starting PC activity tracker for %s minutes", duration_minutes)
    
    end_time = time.time() + (duration_minutes * 60)
    last_title = None

    try:
        while time.time() < end_time:
            current_title = get_active_window_title()
            
            # If the window has changed and it has a valid title...
            if current_title and current_title != last_title:
                # Don't announce meaningless titles like 'Task Switching' or 'Program Manager'
                if current_title not in ["Task Switching", "Program Manager"]:
                    try:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=f"👀 Now viewing:\n`{current_title}`",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.warning("Failed to send tracking alert: %s", e)
                
                last_title = current_title
                
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logger.info("Tracker task was cancelled early.")
        
    finally:
        # Notify user when tracking ends naturally or via cancellation
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="⏹️ *Activity tracking stopped.*",
                parse_mode="Markdown"
            )
        except Exception:
            pass
        
        global _TRACKER_TASK
        _TRACKER_TASK = None


async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /track_actions."""
    global _TRACKER_TASK

    # 1. Parse duration
    duration = 10.0
    if context.args:
        try:
            duration = float(context.args[0])
            if duration <= 0 or duration > 120:  # Cap at 2 hours for safety
                return "⚠️ Please provide a valid number of minutes (max 120)."
        except ValueError:
            return "⚠️ Invalid time format. Try `/track_actions 5`"

    # 2. Check if already running
    if _TRACKER_TASK and not _TRACKER_TASK.done():
        # Stop the old one and start a new one
        _TRACKER_TASK.cancel()
        await update.message.reply_text("🔄 Restarting activity tracker...")
        await asyncio.sleep(0.5)  # brief pause to let the old task cleanup

    # 3. Start the background tracker
    chat_id = update.effective_chat.id
    _TRACKER_TASK = asyncio.create_task(_run_tracker(chat_id, context.bot, duration))
    
    # Return None so bot.py's generic success handler is bypassed. The tracker handles its own replies.
    await update.message.reply_text(
        f"🕵️‍♂️ **Live Tracking Started!**\n"
        f"Monitoring active windows for the next {duration} minutes.\n"
        f"You will get a message instantly whenever the screen switches to a new app.",
        parse_mode="Markdown"
    )
    return None
