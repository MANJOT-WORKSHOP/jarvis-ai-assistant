"""
Jarvis Persistent Memory
─────────────────────────
JSON-backed storage for user preferences, chat history,
and reminders that survive restarts.
"""

import json
import os
import threading
from datetime import datetime

DEFAULT_MEMORY_FILE = "jarvis_memory.json"

DEFAULT_DATA = {
    "user": {
        "name": None,
        "preferred_title": "sir",
    },
    "preferences": {
        "default_city": None,
        "always_listening": False,
        "muted": False,
    },
    "chat_history": [],
    "notes": [],
    "stats": {
        "total_commands": 0,
        "first_use": None,
        "last_use": None,
    },
}


class JarvisMemory:
    """Thread-safe persistent memory backed by a JSON file."""

    def __init__(self, filepath=DEFAULT_MEMORY_FILE):
        self._filepath = filepath
        self._lock = threading.Lock()
        self._data = {}
        self._load()

    # ──────────────────────────────────────────
    #  Load / Save
    # ──────────────────────────────────────────

    def _load(self):
        """Load data from disk, or create defaults."""
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                # Merge any missing default keys
                for key, value in DEFAULT_DATA.items():
                    if key not in self._data:
                        self._data[key] = value
                    elif isinstance(value, dict):
                        for k, v in value.items():
                            if k not in self._data[key]:
                                self._data[key][k] = v
            except (json.JSONDecodeError, Exception) as e:
                print(f"[Memory] Error loading {self._filepath}: {e}")
                self._data = dict(DEFAULT_DATA)
        else:
            self._data = dict(DEFAULT_DATA)
            self._data["stats"]["first_use"] = datetime.now().isoformat()
            self._save()

    def _save(self):
        """Write data to disk."""
        try:
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            print(f"[Memory] Error saving: {e}")

    # ──────────────────────────────────────────
    #  User Profile
    # ──────────────────────────────────────────

    def get_user_name(self):
        with self._lock:
            return self._data["user"].get("name")

    def set_user_name(self, name):
        with self._lock:
            self._data["user"]["name"] = name
            self._save()

    def get_title(self):
        with self._lock:
            return self._data["user"].get("preferred_title", "sir")

    def set_title(self, title):
        with self._lock:
            self._data["user"]["preferred_title"] = title
            self._save()

    # ──────────────────────────────────────────
    #  Preferences
    # ──────────────────────────────────────────

    def get_pref(self, key, default=None):
        with self._lock:
            return self._data["preferences"].get(key, default)

    def set_pref(self, key, value):
        with self._lock:
            self._data["preferences"][key] = value
            self._save()

    def get_default_city(self):
        with self._lock:
            return self._data["preferences"].get("default_city")

    def set_default_city(self, city):
        with self._lock:
            self._data["preferences"]["default_city"] = city
            self._save()

    # ──────────────────────────────────────────
    #  Chat History (last N messages for context)
    # ──────────────────────────────────────────

    def save_chat(self, role, message):
        """Save a chat message to persistent history."""
        with self._lock:
            self._data["chat_history"].append({
                "role": role,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            })
            # Keep last 100 messages
            if len(self._data["chat_history"]) > 100:
                self._data["chat_history"] = self._data["chat_history"][-100:]
            self._save()

    def get_chat_history(self, limit=20):
        with self._lock:
            return self._data["chat_history"][-limit:]

    def clear_chat_history(self):
        with self._lock:
            self._data["chat_history"] = []
            self._save()

    # ──────────────────────────────────────────
    #  Notes
    # ──────────────────────────────────────────

    def add_note(self, note):
        with self._lock:
            self._data["notes"].append({
                "text": note,
                "created": datetime.now().isoformat(),
            })
            self._save()

    def get_notes(self):
        with self._lock:
            return list(self._data["notes"])

    def clear_notes(self):
        with self._lock:
            self._data["notes"] = []
            self._save()

    # ──────────────────────────────────────────
    #  Stats
    # ──────────────────────────────────────────

    def log_command(self):
        with self._lock:
            self._data["stats"]["total_commands"] += 1
            self._data["stats"]["last_use"] = datetime.now().isoformat()
            self._save()

    def get_stats(self):
        with self._lock:
            return dict(self._data["stats"])

    # ──────────────────────────────────────────
    #  Generic access
    # ──────────────────────────────────────────

    def get_all(self):
        with self._lock:
            return dict(self._data)
