"""
tasks/screenshot.py — Capture the PC screen and send it to the Telegram user.

Registered bot command : /screenshot

What it does:
  Uses `mss` to grab the full primary monitor at native resolution,
  converts the raw bitmap to a JPEG (via Pillow), and sends it
  directly as a Telegram photo via reply_photo().

  Because this task calls reply_photo() itself it returns None,
  which tells bot.py's generic handler to skip the default text reply
  so the user only receives the photo.
"""

import asyncio
import io
import logging
from datetime import datetime

import mss
from PIL import Image

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ── Bot command metadata ───────────────────────────────────────────────────────
COMMAND = "screenshot"
DESCRIPTION = "Capture and send a live screenshot of the PC screen"


# ── Screenshot helper (runs in thread pool) ────────────────────────────────────
def _take_screenshot() -> io.BytesIO:
    """
    Grab the primary monitor and return it as a JPEG BytesIO buffer.
    Runs synchronously — call via run_in_executor to avoid blocking the bot.
    """
    with mss.mss() as sct:
        # monitor[0] is "all monitors combined"; monitor[1] is the primary screen
        monitor = sct.monitors[1]
        raw = sct.grab(monitor)

    # Convert the raw mss ScreenShot to a Pillow Image, then to JPEG bytes
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf


# ── Async entry point ──────────────────────────────────────────────────────────
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Called when the user sends /screenshot.
    Captures the screen and sends it as a photo.
    Returns None so bot.py's generic handler skips the text reply.
    """
    loop = asyncio.get_event_loop()
    buf = await loop.run_in_executor(None, _take_screenshot)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    caption = f"🖥️ Screenshot taken at {timestamp}"

    await update.message.reply_photo(photo=buf, caption=caption)
    logger.info("Screenshot sent to user %s", update.effective_user.id)

    # Return None → bot.py generic handler will skip the text reply
    return None
