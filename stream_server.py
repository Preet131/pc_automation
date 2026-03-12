"""
stream_server.py — A lightweight standalone Flask app that serves a live MJPEG stream of the PC screen.

Runs in a background thread started by `tasks/stream.py`.
"""
import io
import time
import logging
import ctypes

from flask import Flask, Response
import mss
from PIL import Image, ImageDraw

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_mouse_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

# Disable typical Flask stdout logging so it doesn't clutter the bot's logs
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

def generate_frames():
    """Generator function that yields JPEG frames endlessly."""
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        while True:
            # Capture
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            
            # Draw the mouse cursor
            mx, my = get_mouse_pos()
            rel_x = mx - monitor["left"]
            rel_y = my - monitor["top"]
            draw = ImageDraw.Draw(img)
            
            # Draw a simple white dot with a red outline to simulate the cursor
            r = 6
            draw.ellipse((rel_x - r, rel_y - r, rel_x + r, rel_y + r), fill="white", outline="red", width=2)
            
            # Compress and format
            buf = io.BytesIO()
            # Quality=60 and slight resize to ensure smooth streaming over tunnels
            img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
            img.save(buf, format="JPEG", quality=60)
            frame = buf.getvalue()
            
            # Yield multipart HTTP chunk
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            
            # Target ~15 FPS
            time.sleep(1/15)

@app.route('/')
def index():
    """Simple HTML page to view the stream."""
    return '''
    <html>
      <head>
        <title>PC Live Stream</title>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0"/>
        <style>
          body { background-color: #000; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
          img { max-width: 100%; max-height: 100%; object-fit: contain; }
        </style>
      </head>
      <body>
        <img id="stream" src="/feed" />
        <script>
            // Auto-reconnect logic if stream hiccups
            const img = document.getElementById('stream');
            img.onerror = () => {
                setTimeout(() => { img.src = "/feed?" + new Date().getTime(); }, 1000);
            };
        </script>
      </body>
    </html>
    '''

@app.route('/feed')
def feed():
    """The MJPEG endpoint."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_server(port=5050):
    """Run the Flask server synchronously."""
    app.run(host='127.0.0.1', port=port, threaded=True, use_reloader=False)

if __name__ == '__main__':
    run_server()
