"""
tasks/stop_stream.py — Command to manually terminate an active live web stream.

Registered bot command : /stop_stream
"""

from telegram import Update
from telegram.ext import ContextTypes

COMMAND = "stop_stream"
DESCRIPTION = "Force-stop the active live web stream"

async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /stop_stream."""
    from tasks.stream import ACTIVE_STREAM, _shutdown_services
    
    if ACTIVE_STREAM["cloudflared_proc"] and ACTIVE_STREAM["cloudflared_proc"].poll() is None:
        await _shutdown_services()
        
        if ACTIVE_STREAM["shutdown_task"] and not ACTIVE_STREAM["shutdown_task"].done():
            ACTIVE_STREAM["shutdown_task"].cancel()
            
        return "⏹️ Live web stream has been terminated."
    else:
        return "ℹ️ No live stream is currently active."
