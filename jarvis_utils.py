"""
Jarvis Utilities
────────────────
Screenshot capture, weather, news, system monitoring,
and reminder management.
"""

import io
import os
import re
import threading
import time
import base64
from datetime import datetime, timedelta

# ── Optional imports ──
try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


# ══════════════════════════════════════════════
#  Screenshot / Vision
# ══════════════════════════════════════════════

def take_screenshot():
    """Capture the primary monitor. Returns PIL Image or None."""
    if not MSS_AVAILABLE or not PIL_AVAILABLE:
        print("[Utils] mss or Pillow not installed for screenshots.")
        return None
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            # Resize to reduce token cost for Gemini (max 1280px wide)
            max_w = 1280
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
            return img
    except Exception as e:
        print(f"[Screenshot Error] {e}")
        return None


def image_to_bytes(img, fmt="PNG"):
    """Convert PIL Image to bytes."""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


# ══════════════════════════════════════════════
#  Weather  (wttr.in — free, no API key)
# ══════════════════════════════════════════════

def get_weather(city=None):
    """Fetch current weather from wttr.in. Returns dict or error string."""
    if not REQUESTS_AVAILABLE:
        return "Requests library not installed."

    if not city:
        city = ""  # wttr.in auto-detects location

    try:
        url = f"https://wttr.in/{city}?format=j1"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Jarvis-AI"})
        resp.raise_for_status()
        data = resp.json()

        current = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]
        location = area.get("areaName", [{"value": city or "your location"}])[0]["value"]
        country = area.get("country", [{"value": ""}])[0]["value"]

        return {
            "location": f"{location}, {country}".strip(", "),
            "temp_c": current.get("temp_C", "?"),
            "temp_f": current.get("temp_F", "?"),
            "feels_like_c": current.get("FeelsLikeC", "?"),
            "description": current.get("weatherDesc", [{"value": "Unknown"}])[0]["value"],
            "humidity": current.get("humidity", "?"),
            "wind_kmph": current.get("windspeedKmph", "?"),
            "wind_dir": current.get("winddir16Point", "?"),
            "visibility_km": current.get("visibility", "?"),
            "uv_index": current.get("uvIndex", "?"),
        }
    except requests.Timeout:
        return "Weather service timed out. Please try again."
    except Exception as e:
        return f"Could not fetch weather: {e}"


def format_weather(data):
    """Convert weather dict to a spoken-friendly string."""
    if isinstance(data, str):
        return data  # error message
    return (
        f"Currently in {data['location']}: {data['description']}, "
        f"{data['temp_c']} degrees Celsius (feels like {data['feels_like_c']}). "
        f"Humidity is {data['humidity']} percent, "
        f"wind {data['wind_kmph']} kilometres per hour from the {data['wind_dir']}."
    )


# ══════════════════════════════════════════════
#  News  (Google News RSS — free, no API key)
# ══════════════════════════════════════════════

def get_news(topic=None, count=5):
    """Fetch top headlines from Google News RSS. Returns list of dicts."""
    if not REQUESTS_AVAILABLE:
        return []

    try:
        if topic:
            url = f"https://news.google.com/rss/search?q={topic}&hl=en"
        else:
            url = "https://news.google.com/rss?hl=en"

        resp = requests.get(url, timeout=10, headers={"User-Agent": "Jarvis-AI"})
        resp.raise_for_status()

        # Simple XML parsing without external library
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")

        headlines = []
        for item in items[:count]:
            title = item.findtext("title", "")
            # Google News titles often end with " - Source Name"
            # Clean it for voice output
            source = ""
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source = parts[1] if len(parts) > 1 else ""

            headlines.append({
                "title": title,
                "source": source,
                "link": item.findtext("link", ""),
                "published": item.findtext("pubDate", ""),
            })

        return headlines
    except Exception as e:
        print(f"[News Error] {e}")
        return []


def format_news(headlines):
    """Convert news list to spoken-friendly string."""
    if not headlines:
        return "I couldn't fetch any news at the moment."

    parts = [f"Here are the top {len(headlines)} headlines."]
    for i, h in enumerate(headlines, 1):
        source_part = f", from {h['source']}" if h["source"] else ""
        parts.append(f"Number {i}: {h['title']}{source_part}.")

    return " ".join(parts)


# ══════════════════════════════════════════════
#  System Monitor  (psutil)
# ══════════════════════════════════════════════

def get_system_stats():
    """Return system resource usage as a dict."""
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not installed."}

    stats = {}
    try:
        # CPU
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        stats["cpu_count"] = psutil.cpu_count()

        # Memory
        mem = psutil.virtual_memory()
        stats["ram_percent"] = mem.percent
        stats["ram_used_gb"] = round(mem.used / (1024 ** 3), 1)
        stats["ram_total_gb"] = round(mem.total / (1024 ** 3), 1)

        # Disk
        disk = psutil.disk_usage("/")
        stats["disk_percent"] = disk.percent
        stats["disk_used_gb"] = round(disk.used / (1024 ** 3), 1)
        stats["disk_total_gb"] = round(disk.total / (1024 ** 3), 1)

        # Battery (may not exist on desktops)
        battery = psutil.sensors_battery()
        if battery:
            stats["battery_percent"] = battery.percent
            stats["battery_plugged"] = battery.power_plugged
            stats["battery_time_left"] = (
                str(timedelta(seconds=battery.secsleft))
                if battery.secsleft > 0 else "Charging"
            )
        else:
            stats["battery_percent"] = None

        # Boot time
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes = remainder // 60
        stats["uptime"] = f"{hours}h {minutes}m"

    except Exception as e:
        stats["error"] = str(e)

    return stats


def format_system_stats(stats):
    """Convert system stats to spoken-friendly string."""
    if "error" in stats:
        return f"I couldn't read system stats: {stats['error']}"

    parts = [
        f"CPU is at {stats['cpu_percent']} percent across {stats['cpu_count']} cores.",
        f"RAM usage is {stats['ram_percent']} percent — "
        f"{stats['ram_used_gb']} of {stats['ram_total_gb']} gigabytes used.",
        f"Disk usage is {stats['disk_percent']} percent — "
        f"{stats['disk_used_gb']} of {stats['disk_total_gb']} gigabytes used.",
    ]

    if stats.get("battery_percent") is not None:
        plug_status = "plugged in" if stats["battery_plugged"] else "on battery"
        parts.append(
            f"Battery is at {stats['battery_percent']} percent, {plug_status}."
        )

    parts.append(f"System uptime: {stats['uptime']}.")

    return " ".join(parts)


# ══════════════════════════════════════════════
#  Reminder Manager
# ══════════════════════════════════════════════

class ReminderManager:
    """Manages timed reminders with voice/callback alerts."""

    def __init__(self, on_reminder=None):
        """
        Args:
            on_reminder: callback(reminder_text) when a reminder fires.
        """
        self.on_reminder = on_reminder
        self._reminders = []  # list of {id, text, fire_at, timer}
        self._lock = threading.Lock()
        self._next_id = 1

    def add(self, text, seconds):
        """Schedule a reminder. Returns reminder ID."""
        with self._lock:
            rid = self._next_id
            self._next_id += 1
            fire_at = datetime.now() + timedelta(seconds=seconds)

            timer = threading.Timer(seconds, self._fire, args=(rid, text))
            timer.daemon = True
            timer.start()

            self._reminders.append({
                "id": rid,
                "text": text,
                "fire_at": fire_at,
                "timer": timer,
                "fired": False,
            })
            return rid

    def _fire(self, rid, text):
        """Called when a reminder timer expires."""
        with self._lock:
            for r in self._reminders:
                if r["id"] == rid:
                    r["fired"] = True
                    break

        if self.on_reminder:
            self.on_reminder(text)

    def list_active(self):
        """Return list of pending reminders."""
        with self._lock:
            now = datetime.now()
            return [
                {
                    "id": r["id"],
                    "text": r["text"],
                    "time_left": str(r["fire_at"] - now).split(".")[0],
                    "fire_at": r["fire_at"].strftime("%I:%M %p"),
                }
                for r in self._reminders
                if not r["fired"]
            ]

    def cancel(self, rid):
        """Cancel a reminder by ID."""
        with self._lock:
            for r in self._reminders:
                if r["id"] == rid and not r["fired"]:
                    r["timer"].cancel()
                    r["fired"] = True
                    return True
        return False

    def cancel_all(self):
        """Cancel all pending reminders."""
        with self._lock:
            for r in self._reminders:
                if not r["fired"]:
                    r["timer"].cancel()
                    r["fired"] = True

    def cleanup(self):
        """Cancel all timers."""
        self.cancel_all()


def parse_reminder(text):
    """Parse 'remind me to X in Y minutes/hours/seconds'.

    Returns (task_text, seconds) or (None, None).
    """
    # Pattern: "remind me to [task] in [number] [unit]"
    pattern = r"remind\s+me\s+to\s+(.+?)\s+in\s+(\d+)\s*(seconds?|minutes?|mins?|hours?|hrs?)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        task = match.group(1).strip()
        amount = int(match.group(2))
        unit = match.group(3).lower()

        if unit.startswith("sec"):
            seconds = amount
        elif unit.startswith("min"):
            seconds = amount * 60
        elif unit.startswith("hr") or unit.startswith("hour"):
            seconds = amount * 3600
        else:
            seconds = amount * 60  # default to minutes

        return task, seconds

    return None, None

# ══════════════════════════════════════════════
#  Clipboard
# ══════════════════════════════════════════════

def get_clipboard():
    """Read text from the Windows clipboard. Returns str or None."""
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return data
        except (TypeError, win32clipboard.error):
            return None
        finally:
            win32clipboard.CloseClipboard()
    except Exception as e:
        print(f"[Clipboard Error] {e}")
        return None


def set_clipboard(text):
    """Write text to the Windows clipboard."""
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(str(text), win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return True
    except Exception as e:
        print(f"[Clipboard Error] {e}")
        return False


# ══════════════════════════════════════════════
#  Camera / Webcam
# ══════════════════════════════════════════════

def capture_camera():
    """Capture a single frame from the default webcam. Returns PIL Image or None."""
    try:
        import cv2
    except ImportError:
        print("[Camera] opencv-python not installed.")
        return None

    if not PIL_AVAILABLE:
        print("[Camera] Pillow not installed.")
        return None

    cap = None
    try:
        # Try DirectShow backend first (more reliable on Windows)
        for cam_index in (0, 1):
            cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
            if cap.isOpened():
                break
            cap.release()
            cap = None

        # Fallback: try without DirectShow
        if cap is None or not cap.isOpened():
            for cam_index in (0, 1):
                cap = cv2.VideoCapture(cam_index)
                if cap.isOpened():
                    break
                cap.release()
                cap = None

        if cap is None or not cap.isOpened():
            print("[Camera] No webcam detected. Check Settings > Privacy > Camera.")
            return None

        # Grab several frames to let the camera auto-expose (first frames are often black)
        for _ in range(5):
            cap.read()

        ret, frame = cap.read()
        if not ret or frame is None:
            print("[Camera] Failed to capture frame.")
            return None

        # Convert BGR (OpenCV) to RGB (PIL)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)

        # Resize if very large
        max_w = 1280
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)

        return img
    except Exception as e:
        print(f"[Camera Error] {e}")
        return None
    finally:
        if cap is not None:
            cap.release()
