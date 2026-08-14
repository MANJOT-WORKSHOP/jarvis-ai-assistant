import os

# ──────────────────────────────────────────────
#  Gemini API
# ──────────────────────────────────────────────
apikey = os.environ.get("GEMINI_API_KEY", "your_gemini_api_key_here")
GEMINI_MODEL = "gemini-3.6-flash"

# ──────────────────────────────────────────────
#  Voice Settings
# ──────────────────────────────────────────────
VOICE_NAME = "en-GB-RyanNeural"   # British male — closest to Jarvis
VOICE_RATE = "-5%"                # Slightly deliberate delivery
VOICE_VOLUME = "+0%"

# ──────────────────────────────────────────────
#  Conversation
# ──────────────────────────────────────────────
MAX_CHAT_HISTORY = 20
USER_TITLE = "sir"

# ──────────────────────────────────────────────
#  Wake Word / Always Listening
# ──────────────────────────────────────────────
WAKE_WORD_ENABLED = False         # Toggle always-listening mode
WAKE_KEYWORD = "jarvis"           # Keyword to listen for
WAKE_LISTEN_TIMEOUT = 3           # Seconds per listening burst
WAKE_PAUSE_BETWEEN = 0.3          # Seconds pause between bursts

# ──────────────────────────────────────────────
#  Global Hotkey
# ──────────────────────────────────────────────
GLOBAL_HOTKEY = "ctrl+j"          # Press to activate Jarvis from anywhere

# ──────────────────────────────────────────────
#  Files & Paths
# ──────────────────────────────────────────────
GEMINI_FILES_DIR = "GeminiFiles"
MEMORY_FILE = "jarvis_memory.json"

# ──────────────────────────────────────────────
#  Available Voices (Edge TTS)
# ──────────────────────────────────────────────
AVAILABLE_VOICES = {
    "British Male (Ryan)": "en-GB-RyanNeural",
    "British Female (Sonia)": "en-GB-SoniaNeural",
    "American Male (Guy)": "en-US-GuyNeural",
    "American Female (Jenny)": "en-US-JennyNeural",
    "American Male (Christopher)": "en-US-ChristopherNeural",
    "Australian Male (William)": "en-AU-WilliamNeural",
    "Indian Male (Prabhat)": "en-IN-PrabhatNeural",
    "Indian Female (Neerja)": "en-IN-NeerjaNeural",
}

# ──────────────────────────────────────────────
#  Themes
# ──────────────────────────────────────────────
THEMES = {
    "arc_reactor": {
        "name": "Arc Reactor",
        "bg": "#0a0e17", "surface": "#111827", "input": "#1e293b",
        "input_border": "#334155", "accent": "#00d4ff", "accent_dim": "#0891b2",
        "accent_glow": "#00f5ff", "text": "#e2e8f0", "text_dim": "#94a3b8",
        "text_jarvis": "#00d4ff", "text_user": "#f1f5f9",
        "green": "#10b981", "amber": "#f59e0b", "red": "#ef4444",
        "btn_surface": "#1e293b", "btn_hover": "#164e63", "monitor_bg": "#0d1321",
        "orb": {"core": "#1a8aff", "ring": "#0a4a7a", "glow": "#00bfff"},
    },
    "iron_man": {
        "name": "Iron Man",
        "bg": "#1a0a05", "surface": "#2d1810", "input": "#3d2418",
        "input_border": "#5c3a2a", "accent": "#ff6b35", "accent_dim": "#cc4a1a",
        "accent_glow": "#ff8c5a", "text": "#fce4d6", "text_dim": "#c4956a",
        "text_jarvis": "#ff6b35", "text_user": "#fff0e6",
        "green": "#10b981", "amber": "#fbbf24", "red": "#ef4444",
        "btn_surface": "#3d2418", "btn_hover": "#5c3a2a", "monitor_bg": "#140a05",
        "orb": {"core": "#ff6b35", "ring": "#8b3a1a", "glow": "#ff8c5a"},
    },
    "stealth": {
        "name": "Stealth",
        "bg": "#0a0a0a", "surface": "#161616", "input": "#222222",
        "input_border": "#3a3a3a", "accent": "#e0e0e0", "accent_dim": "#888888",
        "accent_glow": "#ffffff", "text": "#d4d4d4", "text_dim": "#777777",
        "text_jarvis": "#e0e0e0", "text_user": "#f5f5f5",
        "green": "#10b981", "amber": "#f59e0b", "red": "#ef4444",
        "btn_surface": "#222222", "btn_hover": "#333333", "monitor_bg": "#080808",
        "orb": {"core": "#cccccc", "ring": "#555555", "glow": "#ffffff"},
    },
    "matrix": {
        "name": "Matrix",
        "bg": "#050a05", "surface": "#0a160a", "input": "#122012",
        "input_border": "#1a3a1a", "accent": "#00ff41", "accent_dim": "#00b330",
        "accent_glow": "#39ff73", "text": "#c8f7d0", "text_dim": "#5a9a62",
        "text_jarvis": "#00ff41", "text_user": "#e0ffe6",
        "green": "#00ff41", "amber": "#f59e0b", "red": "#ef4444",
        "btn_surface": "#122012", "btn_hover": "#1a3a1a", "monitor_bg": "#030803",
        "orb": {"core": "#00cc33", "ring": "#005a15", "glow": "#39ff73"},
    },
}