"""
tasks/live.py — Provide a live stream of the PC screen using Telegram message updates.

Registered bot command : /live

What it does:
  Takes a screenshot and sends it to the user. Then, it enters a loop for 30
  seconds, taking a new screenshot every 2 seconds and replacing the photo
  in the *same* Telegram message. This creates a clean animation without
  flooding the chat history.
"""

import asyncio
import io
import logging
import time
from datetime import datetime

import mss
from PIL import Image

from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# ── Bot command metadata ───────────────────────────────────────────────────────
COMMAND = "live"
DESCRIPTION = "Watch a live 30-sec stream of the PC screen"

# ── Constants ──────────────────────────────────────────────────────────────────
LIVE_DURATION = 30       # seconds to stream
INTERVAL = 2.0           # seconds between frames


# ── Screenshot helper (runs in thread pool) ────────────────────────────────────
def _take_screenshot() -> io.BytesIO:
    """Capture the primary monitor, scale it slightly for speed, and return a JPEG."""
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        
    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    
    # Optional: resize down slightly to make uploads faster for streaming
    # img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
    
    buf = io.BytesIO()
    # Use quality=60 for streaming to save bandwidth and speed up Telegram delivery
    img.save(buf, format="JPEG", quality=60)
    buf.seek(0)
    return buf


# ── Async entry point ──────────────────────────────────────────────────────────
async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Called when the user sends /live.
    Takes an initial screenshot, sends it, then updates it in a loop.
    Returns None to suppress bot.py's default success message.
    """
    loop = asyncio.get_event_loop()
    user_id = update.effective_user.id
    
    # 1. Take and send the first frame
    buf = await loop.run_in_executor(None, _take_screenshot)
    caption = f"🔴 *LIVE* — Streaming for {LIVE_DURATION}s (_0s_)"
    
    message = await update.message.reply_photo(
        photo=buf, 
        caption=caption,
        parse_mode="Markdown"
    )
    
    logger.info("Started /live stream for user %s", user_id)
    
    # 2. Enter the live stream loop
    start_time = time.time()
    frames_sent = 1
    
    while True:
        elapsed = time.time() - start_time
        if elapsed >= LIVE_DURATION:
            break
            
        # Wait until the next interval slot
        # (subtracting execution time to keep a steady framerate)
        await asyncio.sleep(max(0, INTERVAL - (time.time() - start_time) % INTERVAL))
        
        try:
            # Capture next frame
            new_buf = await loop.run_in_executor(None, _take_screenshot)
            new_caption = f"🔴 *LIVE* — Streaming for {LIVE_DURATION}s (_{int(elapsed)}s_)"
            
            # Edit the existing message with the new photo
            media = InputMediaPhoto(media=new_buf, caption=new_caption, parse_mode="Markdown")
            await context.bot.edit_message_media(
                chat_id=user_id,
                message_id=message.message_id,
                media=media
            )
            frames_sent += 1
            
        except Exception as exc:
            # Telegram might complain if the auto-resize produces identical bytes, 
            # or if rate limits are hit. We just log and continue.
            if "Message is not modified" not in str(exc):
                logger.warning("Error editing live frame: %s", exc)
                await asyncio.sleep(1) # Back off slightly on error
    
    # 3. Finalize the stream
    try:
        final_buf = await loop.run_in_executor(None, _take_screenshot)
        timestamp = datetime.now().strftime("%H:%M:%S")
        final_caption = f"⏹️ *Live stream ended* at {timestamp} ({frames_sent} frames sent)"
        
        final_media = InputMediaPhoto(media=final_buf, caption=final_caption, parse_mode="Markdown")
        await context.bot.edit_message_media(
            chat_id=user_id,
            message_id=message.message_id,
            media=final_media
        )
    except Exception as exc:
        logger.warning("Failed to set final live frame: %s", exc)

    logger.info("Ended /live stream for user %s", user_id)
    
    # Return None so bot.py doesn't send the extra text reply
    return None
