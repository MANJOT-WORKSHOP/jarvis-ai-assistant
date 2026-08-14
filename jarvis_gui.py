"""
Jarvis GUI Dashboard  v5
────────────────────────
Premium dark-themed desktop UI with animated orb, chat history,
system monitor, tray icon, global hotkey, wake word toggle,
cinematic boot sequence, typing animation, sound effects.
"""

import customtkinter as ctk
import tkinter as tk
import threading
import queue
import math
import time
import datetime

from jarvis_voice import VoiceEngine
from jarvis_brain import JarvisBrain
from config import WAKE_KEYWORD, WAKE_LISTEN_TIMEOUT, WAKE_PAUSE_BETWEEN, GLOBAL_HOTKEY
from jarvis_memory import JarvisMemory
from config import THEMES, AVAILABLE_VOICES
import jarvis_sounds

# ── Optional imports ──
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import pystray
    from PIL import Image as PilImage, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

try:
    import keyboard as kb_lib
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# ──────────────────────────────────────────────
#  Colour Palette  (Arc Reactor aesthetic)
# ──────────────────────────────────────────────

# Load theme from memory at module level
def _load_theme():
    """Load the active theme colors from memory."""
    try:
        mem = JarvisMemory()
        theme_name = mem.get_pref("theme", "arc_reactor")
    except Exception:
        theme_name = "arc_reactor"
    theme = THEMES.get(theme_name, THEMES["arc_reactor"])
    return theme

_active_theme = _load_theme()

C = {k: v for k, v in _active_theme.items() if k not in ("name", "orb")}

ORB = {
    "idle":       _active_theme.get("orb", {"core": "#1a8aff", "ring": "#0a4a7a", "glow": "#00bfff"}),
    "listening":  {"core": "#00e5ff", "ring": "#00897b", "glow": "#18ffff"},
    "processing": {"core": "#ff9100", "ring": "#e65100", "glow": "#ffab40"},
    "speaking":   {"core": "#00e676", "ring": "#1b5e20", "glow": "#69f0ae"},
    "error":      {"core": "#ff1744", "ring": "#b71c1c", "glow": "#ff5252"},
}

ANIM = {
    "idle":       {"speed": 0.03, "amplitude": 0.08},
    "listening":  {"speed": 0.08, "amplitude": 0.15},
    "processing": {"speed": 0.12, "amplitude": 0.10},
    "speaking":   {"speed": 0.06, "amplitude": 0.12},
    "error":      {"speed": 0.15, "amplitude": 0.20},
}

DOT_COUNT = {"idle": 3, "listening": 6, "processing": 4, "speaking": 5, "error": 2}
DOT_SPEED = {"idle": 1.0, "listening": 2.0, "processing": 3.0, "speaking": 1.5, "error": 4.0}


def blend(hex1, hex2, alpha):
    r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
    r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    r = int(r1 * alpha + r2 * (1 - alpha))
    g = int(g1 * alpha + g2 * (1 - alpha))
    b = int(b1 * alpha + b2 * (1 - alpha))
    return f"#{r:02x}{g:02x}{b:02x}"


# ══════════════════════════════════════════════
#  Main GUI Class
# ══════════════════════════════════════════════

class JarvisGUI:

    def __init__(self):
        self.state = "idle"
        self.phase = 0.0
        self.msg_queue = queue.Queue()
        self._tray_icon = None
        self._hotkey_registered = False

        # Modules
        self.voice = VoiceEngine(on_state_change=self._voice_state_cb)
        self.brain = JarvisBrain(on_reminder=self._on_reminder)

        # Build UI
        self._create_window()
        self._create_title()
        self._create_orb()
        self._create_status()
        self._create_chat()
        self._create_input()
        self._create_quick_buttons()
        self._create_monitor_bar()

        # Start loops
        self._animate()
        self._poll()
        self._start_monitor_update()
        self._setup_global_hotkey()

    # ══════════════════════════════════════════
    #  Window
    # ══════════════════════════════════════════

    def _create_window(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.root = ctk.CTk()
        self.root.title("J.A.R.V.I.S")
        self.root.geometry("560x850")
        self.root.minsize(500, 700)
        self.root.configure(fg_color=C["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_minimize_to_tray)
        self.root.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self._exit_fullscreen())
        self._is_fullscreen = False

    # ══════════════════════════════════════════
    #  Title
    # ══════════════════════════════════════════

    def _create_title(self):
        sep = tk.Canvas(self.root, height=2, bg=C["bg"], highlightthickness=0)
        sep.pack(fill="x", padx=40, pady=(15, 0))
        sep.create_line(0, 1, 700, 1, fill=C["accent_dim"], width=1)

        title = ctk.CTkLabel(
            self.root, text="J . A . R . V . I . S",
            font=("Consolas", 28, "bold"), text_color=C["accent"],
        )
        title.pack(pady=(10, 2))

        subtitle = ctk.CTkLabel(
            self.root, text="Just A Rather Very Intelligent System",
            font=("Segoe UI", 11), text_color=C["text_dim"],
        )
        subtitle.pack(pady=(0, 6))

        sep2 = tk.Canvas(self.root, height=2, bg=C["bg"], highlightthickness=0)
        sep2.pack(fill="x", padx=40, pady=(0, 3))
        sep2.create_line(0, 1, 700, 1, fill=C["accent_dim"], width=1)

    # ══════════════════════════════════════════
    #  Animated Orb
    # ══════════════════════════════════════════

    def _create_orb(self):
        self.orb_size = 200
        self.orb_cx = self.orb_size // 2
        self.orb_cy = self.orb_size // 2

        self.canvas = tk.Canvas(
            self.root, width=self.orb_size, height=self.orb_size,
            bg=C["bg"], highlightthickness=0, bd=0,
        )
        self.canvas.pack(pady=(3, 0))

    def _animate(self):
        self.canvas.delete("all")
        cx, cy = self.orb_cx, self.orb_cy
        colors = ORB.get(self.state, ORB["idle"])
        params = ANIM.get(self.state, ANIM["idle"])

        pulse = math.sin(self.phase) * params["amplitude"] + (1.0 - params["amplitude"])

        for i in range(6):
            r = (75 - i * 7) * pulse
            a = 0.08 + i * 0.04
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                     outline=blend(colors["glow"], C["bg"], a), width=1)

        r_outer = 55 * pulse
        self.canvas.create_oval(cx-r_outer, cy-r_outer, cx+r_outer, cy+r_outer,
                                 outline=colors["ring"], width=2)

        r_mid = 45 * pulse
        self.canvas.create_oval(cx-r_mid, cy-r_mid, cx+r_mid, cy+r_mid,
                                 outline=blend(colors["core"], colors["ring"], 0.5), width=1)

        r_core = 30 * pulse
        self.canvas.create_oval(cx-r_core, cy-r_core, cx+r_core, cy+r_core,
                                 fill=colors["core"], outline=colors["glow"], width=1)

        r_dot = 7
        self.canvas.create_oval(cx-r_dot, cy-r_dot, cx+r_dot, cy+r_dot,
                                 fill="#ffffff", outline="")

        n_dots = DOT_COUNT.get(self.state, 3)
        spd = DOT_SPEED.get(self.state, 1.0)
        orbit_r = 60 * pulse
        for i in range(n_dots):
            angle = self.phase * spd + (i * 2 * math.pi / n_dots)
            dx, dy = math.cos(angle) * orbit_r, math.sin(angle) * orbit_r
            pr = 3
            self.canvas.create_oval(cx+dx-pr, cy+dy-pr, cx+dx+pr, cy+dy+pr,
                                     fill=colors["glow"], outline="")

        if self.state == "processing":
            arc_start = (self.phase * 120) % 360
            for offset in (0, 180):
                self.canvas.create_arc(
                    cx-65, cy-65, cx+65, cy+65,
                    start=(arc_start+offset) % 360, extent=80,
                    style="arc", outline=colors["glow"], width=2)

        self.phase += params["speed"]
        self.canvas.after(33, self._animate)

    # ══════════════════════════════════════════
    #  Status Label
    # ══════════════════════════════════════════

    def _create_status(self):
        self.status_label = ctk.CTkLabel(
            self.root, text="◎ INITIALIZING",
            font=("Consolas", 13, "bold"), text_color=C["text_dim"],
        )
        self.status_label.pack(pady=(0, 6))

    def _update_status(self, state):
        labels = {
            "idle":       ("●  ONLINE",     C["accent"]),
            "listening":  ("◉  LISTENING",  C["green"]),
            "processing": ("◎  PROCESSING", C["amber"]),
            "speaking":   ("◉  SPEAKING",   C["green"]),
            "error":      ("✖  ERROR",      C["red"]),
        }
        text, color = labels.get(state, labels["idle"])
        self.status_label.configure(text=text, text_color=color)

    # ══════════════════════════════════════════
    #  Chat History
    # ══════════════════════════════════════════

    def _create_chat(self):
        frame = ctk.CTkFrame(self.root, fg_color=C["surface"], corner_radius=14)
        frame.pack(fill="both", expand=True, padx=16, pady=(0, 6))

        self.chat_box = ctk.CTkTextbox(
            frame, font=("Segoe UI", 13), fg_color=C["surface"],
            text_color=C["text"], wrap="word", state="disabled",
            corner_radius=14, activate_scrollbars=True,
        )
        self.chat_box.pack(fill="both", expand=True, padx=6, pady=6)

        self.chat_box._textbox.tag_config("user_label",   foreground=C["text_user"],   font=("Segoe UI", 13, "bold"))
        self.chat_box._textbox.tag_config("user_text",    foreground=C["text_user"])
        self.chat_box._textbox.tag_config("jarvis_label", foreground=C["text_jarvis"], font=("Segoe UI", 13, "bold"))
        self.chat_box._textbox.tag_config("jarvis_text",  foreground=C["text_jarvis"])
        self.chat_box._textbox.tag_config("system",       foreground=C["text_dim"],    font=("Segoe UI", 11, "italic"))
        self.chat_box._textbox.tag_config("reminder",     foreground=C["amber"],       font=("Segoe UI", 13, "bold"))

    def _append_msg(self, sender, text, msg_type="system"):
        self.chat_box.configure(state="normal")
        if sender:
            label_tag = f"{msg_type}_label" if msg_type in ("user", "jarvis") else msg_type
            text_tag  = f"{msg_type}_text"  if msg_type in ("user", "jarvis") else msg_type
            self.chat_box._textbox.insert("end", f"{sender}:  ", label_tag)
            self.chat_box._textbox.insert("end", f"{text}\n\n", text_tag)
        else:
            self.chat_box._textbox.insert("end", f"{text}\n", msg_type)
        self.chat_box.configure(state="disabled")
        self.chat_box._textbox.see("end")

    # ══════════════════════════════════════════
    #  Input Bar
    # ══════════════════════════════════════════

    def _create_input(self):
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(fill="x", padx=16, pady=(0, 6))

        self.entry = ctk.CTkEntry(
            frame, placeholder_text="  Type a command or press 🎤 to speak…",
            font=("Segoe UI", 13), fg_color=C["input"], text_color=C["text"],
            border_color=C["input_border"], border_width=1,
            corner_radius=22, height=44,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self._on_enter)

        # Wake word toggle
        self._wake_on = False
        self.wake_btn = ctk.CTkButton(
            frame, text="👂", width=44, height=44,
            font=("Segoe UI", 18), fg_color=C["btn_surface"],
            hover_color=C["btn_hover"], corner_radius=22,
            command=self._toggle_wake,
        )
        self.wake_btn.pack(side="right", padx=(0, 6))

        # Mic button
        self.mic_btn = ctk.CTkButton(
            frame, text="🎤", width=48, height=48,
            font=("Segoe UI", 20), fg_color=C["accent_dim"],
            hover_color=C["accent"], corner_radius=24,
            command=self._on_mic,
        )
        self.mic_btn.pack(side="right")

    # ══════════════════════════════════════════
    #  Quick-Access Buttons
    # ══════════════════════════════════════════

    def _create_quick_buttons(self):
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(fill="x", padx=16, pady=(0, 4))

        buttons = [
            ("▶ YouTube",  "open youtube"),
            ("✉ Gmail",    "open gmail"),
            ("🔍 Google",  "open google"),
            ("⏱ Time",     "what is the time"),
            ("🌤 Weather",  "weather"),
            ("📰 News",    "news"),
            ("❓ Help",    "help"),
            ("\u2699 Settings", None),  # Settings opens a dialog, not a command
        ]

        for label, cmd in buttons:
            if cmd is None:
                ctk.CTkButton(
                    frame, text=label, font=("Segoe UI", 10),
                    fg_color=C["btn_surface"], hover_color=C["btn_hover"],
                    corner_radius=8, height=30,
                    command=self._open_settings,
                ).pack(side="left", expand=True, fill="x", padx=2)
            else:
                ctk.CTkButton(
                    frame, text=label, font=("Segoe UI", 10),
                    fg_color=C["btn_surface"], hover_color=C["btn_hover"],
                    corner_radius=8, height=30,
                    command=lambda c=cmd: self._quick(c),
                ).pack(side="left", expand=True, fill="x", padx=2)

    # ══════════════════════════════════════════
    #  System Monitor Bar
    # ══════════════════════════════════════════

    def _create_monitor_bar(self):
        self.monitor_frame = ctk.CTkFrame(
            self.root, fg_color=C["monitor_bg"], corner_radius=0, height=32,
        )
        self.monitor_frame.pack(fill="x", side="bottom")
        self.monitor_frame.pack_propagate(False)

        self.mon_cpu = ctk.CTkLabel(
            self.monitor_frame, text="CPU: --%",
            font=("Consolas", 11), text_color=C["text_dim"],
        )
        self.mon_cpu.pack(side="left", padx=(12, 15))

        self.mon_ram = ctk.CTkLabel(
            self.monitor_frame, text="RAM: --%",
            font=("Consolas", 11), text_color=C["text_dim"],
        )
        self.mon_ram.pack(side="left", padx=(0, 15))

        self.mon_bat = ctk.CTkLabel(
            self.monitor_frame, text="",
            font=("Consolas", 11), text_color=C["text_dim"],
        )
        self.mon_bat.pack(side="left", padx=(0, 15))

        self.mon_hotkey = ctk.CTkLabel(
            self.monitor_frame, text=f"⌨ {GLOBAL_HOTKEY.upper()}",
            font=("Consolas", 11), text_color=C["accent_dim"],
        )
        self.mon_hotkey.pack(side="right", padx=(0, 12))

        self.mon_wake_status = ctk.CTkLabel(
            self.monitor_frame, text="",
            font=("Consolas", 11), text_color=C["text_dim"],
        )
        self.mon_wake_status.pack(side="right", padx=(0, 12))

    def _start_monitor_update(self):
        self._update_monitor()

    def _update_monitor(self):
        if PSUTIL_AVAILABLE:
            try:
                cpu = psutil.cpu_percent(interval=0)
                ram = psutil.virtual_memory().percent

                cpu_color = C["green"] if cpu < 50 else C["amber"] if cpu < 80 else C["red"]
                ram_color = C["green"] if ram < 60 else C["amber"] if ram < 85 else C["red"]

                self.mon_cpu.configure(text=f"CPU: {cpu:.0f}%", text_color=cpu_color)
                self.mon_ram.configure(text=f"RAM: {ram:.0f}%", text_color=ram_color)

                bat = psutil.sensors_battery()
                if bat:
                    plug = "⚡" if bat.power_plugged else "🔋"
                    bat_color = C["green"] if bat.percent > 30 else C["amber"] if bat.percent > 10 else C["red"]
                    self.mon_bat.configure(text=f"{plug} {bat.percent:.0f}%", text_color=bat_color)
            except Exception:
                pass

        self.root.after(3000, self._update_monitor)

    # ══════════════════════════════════════════
    #  System Tray
    # ══════════════════════════════════════════

    def _create_tray_icon_image(self):
        """Create a simple blue circle icon for the tray."""
        img = PilImage.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill=(0, 212, 255, 255), outline=(0, 139, 178, 255), width=2)
        draw.ellipse([24, 24, 40, 40], fill=(255, 255, 255, 255))
        return img

    def _setup_tray(self):
        if not TRAY_AVAILABLE:
            return

        icon_img = self._create_tray_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show Jarvis", self._tray_show),
            pystray.MenuItem("Quit", self._tray_quit),
        )
        self._tray_icon = pystray.Icon("jarvis", icon_img, "J.A.R.V.I.S", menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _tray_show(self, *_args):
        self.msg_queue.put(("show_window",))

    def _tray_quit(self, *_args):
        self.msg_queue.put(("quit",))

    def _on_minimize_to_tray(self):
        """Minimize to tray on window close (if tray available), else quit."""
        if TRAY_AVAILABLE and self._tray_icon:
            self.root.withdraw()
        else:
            self._on_close()

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    # ══════════════════════════════════════════
    #  Global Hotkey
    # ══════════════════════════════════════════

    def _setup_global_hotkey(self):
        if not KEYBOARD_AVAILABLE:
            return
        try:
            kb_lib.add_hotkey(GLOBAL_HOTKEY, self._on_hotkey)
            self._hotkey_registered = True
            print(f"[Hotkey] {GLOBAL_HOTKEY.upper()} registered")
        except Exception as e:
            print(f"[Hotkey Error] {e}")

    def _on_hotkey(self):
        self.msg_queue.put(("hotkey",))

    # ══════════════════════════════════════════
    #  Wake Word Toggle
    # ══════════════════════════════════════════

    def _toggle_wake(self):
        if self._wake_on:
            self._wake_on = False
            self.voice.stop_always_listening()
            self.wake_btn.configure(fg_color=C["btn_surface"])
            self.mon_wake_status.configure(text="")
            self._append_msg(None, "Always-listening mode OFF.", "system")
        else:
            self._wake_on = True
            self.voice.start_always_listening(
                keyword=WAKE_KEYWORD,
                on_wake=self._on_wake_detected,
                listen_timeout=WAKE_LISTEN_TIMEOUT,
                pause=WAKE_PAUSE_BETWEEN,
            )
            self.wake_btn.configure(fg_color=C["green"])
            self.mon_wake_status.configure(text=f"👂 \"{WAKE_KEYWORD}\"", text_color=C["green"])
            self._append_msg(None, f'Always-listening mode ON. Say "{WAKE_KEYWORD}" to activate.', "system")

    def _on_wake_detected(self):
        self.msg_queue.put(("wake_detected",))

    # ══════════════════════════════════════════
    #  Event Handlers
    # ══════════════════════════════════════════

    def _on_enter(self, _event=None):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self._handle_input(text)

    def _on_mic(self):
        # If already listening, don't double-listen
        if self.voice.is_listening:
            return
        # If Jarvis is speaking, interrupt him and start listening
        if self.voice.is_speaking:
            self.voice.stop_speaking()
            time.sleep(0.2)  # brief pause for audio to stop
        threading.Thread(target=self._mic_worker, daemon=True).start()

    def _mic_worker(self):
        jarvis_sounds.play("listen")
        self.msg_queue.put(("state", "listening"))
        query = self.voice.listen()
        if query:
            self.msg_queue.put(("user_input", query))
        else:
            self.msg_queue.put(("state", "idle"))
            self.msg_queue.put(("system_msg", "I didn't catch that. Try again or type your command."))

    def _quick(self, cmd):
        self._handle_input(cmd)

    def _handle_input(self, text):
        self._append_msg("You", text, "user")
        self._set_state("processing")
        threading.Thread(target=self._process_worker, args=(text,), daemon=True).start()

    def _process_worker(self, text):
        response, should_continue = self.brain.process_command(text)
        self.msg_queue.put(("response", response, should_continue))

    def _voice_state_cb(self, state):
        self.msg_queue.put(("state", state))

    def _on_reminder(self, reminder_text):
        self.msg_queue.put(("reminder", reminder_text))

    # ══════════════════════════════════════════
    #  Message Queue Polling
    # ══════════════════════════════════════════

    def _poll(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                kind = msg[0]

                if kind == "state":
                    self._set_state(msg[1])

                elif kind == "user_input":
                    self._handle_input(msg[1])

                elif kind == "response":
                    jarvis_sounds.play("complete")
                    self._type_message("Jarvis", msg[1], "jarvis")
                    self._set_state("idle")
                    self.voice.speak(msg[1])
                    if not msg[2]:  # should_continue = False
                        self.root.after(4000, self._on_close)

                elif kind == "system_msg":
                    self._append_msg(None, msg[1], "system")

                elif kind == "greeting":
                    jarvis_sounds.play("boot")
                    self._type_message("Jarvis", msg[1], "jarvis")
                    self.voice.speak(msg[1])

                elif kind == "boot_step":
                    jarvis_sounds.play("tick")
                    self._append_msg(None, msg[1], "system")

                elif kind == "reminder":
                    alert = f"⏰ Reminder: {msg[1]}"
                    self._append_msg("Jarvis", alert, "jarvis")
                    self.voice.speak(f"Reminder, {msg[1]}")
                    self._show_window()  # bring window to front

                elif kind == "show_window":
                    self._show_window()

                elif kind == "hotkey":
                    self._show_window()
                    if self.voice.is_listening:
                        pass  # already listening
                    else:
                        if self.voice.is_speaking:
                            self.voice.stop_speaking()
                        threading.Thread(target=self._mic_worker, daemon=True).start()

                elif kind == "wake_detected":
                    self._show_window()
                    if self.voice.is_listening:
                        pass  # already listening
                    else:
                        if self.voice.is_speaking:
                            self.voice.stop_speaking()
                        self._append_msg(None, f'Wake word "{WAKE_KEYWORD}" detected!', "system")
                        threading.Thread(target=self._mic_worker, daemon=True).start()

                elif kind == "quit":
                    self._on_close()

        except queue.Empty:
            pass

        self.root.after(80, self._poll)

    # ══════════════════════════════════════════
    #  Typing Animation
    # ══════════════════════════════════════════

    def _type_message(self, sender, text, msg_type):
        """Show sender label instantly, then type the message char by char."""
        self.chat_box.configure(state="normal")
        if sender:
            label_tag = f"{msg_type}_label"
            self.chat_box._textbox.insert("end", f"{sender}:  ", label_tag)
        self.chat_box.configure(state="disabled")
        text_tag = f"{msg_type}_text"
        # Adaptive speed: faster for longer messages
        speed = 18 if len(text) < 120 else 10 if len(text) < 300 else 5
        self._type_chars(text + "\n\n", text_tag, 0, speed)

    def _type_chars(self, text, tag, idx, speed):
        """Animate one character at a time."""
        if idx < len(text):
            self.chat_box.configure(state="normal")
            self.chat_box._textbox.insert("end", text[idx], tag)
            self.chat_box._textbox.see("end")
            self.chat_box.configure(state="disabled")
            self.root.after(speed, self._type_chars, text, tag, idx + 1, speed)

    # ══════════════════════════════════════════
    #  Fullscreen / Presentation Mode
    # ══════════════════════════════════════════

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode (F11)."""
        self._is_fullscreen = not self._is_fullscreen
        self.root.attributes("-fullscreen", self._is_fullscreen)
        if self._is_fullscreen:
            self.msg_queue.put(("system_msg", "  Presentation mode ON  (F11 or Esc to exit)"))
        else:
            self.msg_queue.put(("system_msg", "  Presentation mode OFF"))

    def _exit_fullscreen(self):
        """Exit fullscreen on Escape."""
        if self._is_fullscreen:
            self._is_fullscreen = False
            self.root.attributes("-fullscreen", False)

    # ══════════════════════════════════════════
    #  State
    # ══════════════════════════════════════════

    def _set_state(self, state):
        self.state = state
        self._update_status(state)

    # ══════════════════════════════════════════
    #  Init & Run
    # ══════════════════════════════════════════

    def initialize(self):
        self._append_msg(None, "Initializing systems…", "system")
        threading.Thread(target=self._init_worker, daemon=True).start()

    def _init_worker(self):
        success = self.brain.initialize()
        if success is True:
            self.msg_queue.put(("state", "idle"))
            # Restore saved voice settings
            saved_voice = self.brain.memory.get_pref("voice")
            saved_rate = self.brain.memory.get_pref("voice_rate")
            if saved_voice:
                self.voice.set_voice(saved_voice)
            if saved_rate:
                self.voice.set_rate(saved_rate)
            self.msg_queue.put(("system_msg", "✓  All systems online.  Gemini connected."))

            features = []
            if TRAY_AVAILABLE:
                features.append("system tray")
            if KEYBOARD_AVAILABLE and self._hotkey_registered:
                features.append(f"hotkey ({GLOBAL_HOTKEY.upper()})")
            if PSUTIL_AVAILABLE:
                features.append("system monitor")
            if features:
                self.msg_queue.put(("system_msg", f"✓  Active: {', '.join(features)}"))

            greeting = self.brain.get_greeting()
            self.msg_queue.put(("greeting", greeting))
        else:
            self.msg_queue.put(("state", "error"))
            msg = success if isinstance(success, str) else "⚠  API key validation failed. Update config.py or set GEMINI_API_KEY env var."
            self.msg_queue.put(("system_msg", f"⚠  {msg}" if not msg.startswith("⚠") else msg))

    def run(self):
        self._setup_tray()
        self.initialize()
        self.root.mainloop()

    # ══════════════════════════════════════════
    #  Settings Panel
    # ══════════════════════════════════════════

    def _open_settings(self):
        """Open a settings dialog for voice, theme, and preferences."""
        if hasattr(self, '_settings_win') and self._settings_win is not None:
            try:
                self._settings_win.focus()
                return
            except Exception:
                pass

        win = ctk.CTkToplevel(self.root)
        win.title("Jarvis Settings")
        win.geometry("450x520")
        win.configure(fg_color=C["bg"])
        win.transient(self.root)
        win.grab_set()
        self._settings_win = win

        def on_close():
            self._settings_win = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

        # Title
        ctk.CTkLabel(
            win, text="\u2699  Settings",
            font=("Consolas", 22, "bold"), text_color=C["accent"],
        ).pack(pady=(18, 15))

        # ── Voice Section ──
        ctk.CTkLabel(
            win, text="VOICE", font=("Consolas", 12, "bold"),
            text_color=C["text_dim"],
        ).pack(anchor="w", padx=25)

        voice_frame = ctk.CTkFrame(win, fg_color=C["surface"], corner_radius=10)
        voice_frame.pack(fill="x", padx=20, pady=(5, 10))

        # Voice selector
        voice_names = list(AVAILABLE_VOICES.keys())
        current_voice_id = self.voice.get_current_voice()
        current_voice_label = next(
            (k for k, v in AVAILABLE_VOICES.items() if v == current_voice_id),
            voice_names[0]
        )

        voice_var = ctk.StringVar(value=current_voice_label)
        ctk.CTkLabel(
            voice_frame, text="Voice:", font=("Segoe UI", 13),
            text_color=C["text"],
        ).pack(anchor="w", padx=15, pady=(10, 2))
        voice_menu = ctk.CTkOptionMenu(
            voice_frame, variable=voice_var, values=voice_names,
            font=("Segoe UI", 12), fg_color=C["input"],
            button_color=C["accent_dim"], button_hover_color=C["accent"],
            dropdown_fg_color=C["surface"],
        )
        voice_menu.pack(fill="x", padx=15, pady=(0, 5))

        # Speed slider
        ctk.CTkLabel(
            voice_frame, text="Speed:", font=("Segoe UI", 13),
            text_color=C["text"],
        ).pack(anchor="w", padx=15, pady=(5, 2))

        speed_label = ctk.CTkLabel(
            voice_frame, text="Normal", font=("Consolas", 11),
            text_color=C["accent"],
        )
        speed_label.pack(anchor="w", padx=15)

        def on_speed_change(val):
            v = int(val)
            if v == 0:
                speed_label.configure(text="Normal")
            elif v > 0:
                speed_label.configure(text=f"+{v}% faster")
            else:
                speed_label.configure(text=f"{v}% slower")

        speed_slider = ctk.CTkSlider(
            voice_frame, from_=-30, to=30, number_of_steps=12,
            fg_color=C["input"], progress_color=C["accent_dim"],
            button_color=C["accent"], button_hover_color=C["accent_glow"],
            command=on_speed_change,
        )
        speed_slider.set(0)
        speed_slider.pack(fill="x", padx=15, pady=(0, 10))

        # Preview button
        def preview():
            voice_id = AVAILABLE_VOICES.get(voice_var.get(), AVAILABLE_VOICES[voice_names[0]])
            rate_val = int(speed_slider.get())
            rate_str = f"+{rate_val}%" if rate_val >= 0 else f"{rate_val}%"
            self.voice.set_voice(voice_id)
            self.voice.set_rate(rate_str)
            self.voice.speak("Good evening, sir. How does this voice sound?")

        ctk.CTkButton(
            voice_frame, text="\u25B6  Preview Voice", font=("Segoe UI", 12),
            fg_color=C["accent_dim"], hover_color=C["accent"],
            corner_radius=8, height=34, command=preview,
        ).pack(fill="x", padx=15, pady=(0, 12))

        # ── Theme Section ──
        ctk.CTkLabel(
            win, text="THEME", font=("Consolas", 12, "bold"),
            text_color=C["text_dim"],
        ).pack(anchor="w", padx=25, pady=(5, 0))

        theme_frame = ctk.CTkFrame(win, fg_color=C["surface"], corner_radius=10)
        theme_frame.pack(fill="x", padx=20, pady=(5, 10))

        # Get current theme
        try:
            current_theme = self.brain.memory.get_pref("theme", "arc_reactor")
        except Exception:
            current_theme = "arc_reactor"

        theme_var = ctk.StringVar(value=current_theme)
        theme_options = list(THEMES.keys())
        theme_labels = [THEMES[t]["name"] for t in theme_options]

        for i, (theme_key, theme_label) in enumerate(zip(theme_options, theme_labels)):
            color_preview = THEMES[theme_key]["accent"]
            rb = ctk.CTkRadioButton(
                theme_frame, text=f"  {theme_label}",
                font=("Segoe UI", 13), text_color=C["text"],
                variable=theme_var, value=theme_key,
                fg_color=color_preview, hover_color=color_preview,
                border_color=C["text_dim"],
            )
            rb.pack(anchor="w", padx=15, pady=(8 if i == 0 else 3, 3 if i < len(theme_options)-1 else 8))

        # ── Save Button ──
        def save_settings():
            # Save voice
            voice_id = AVAILABLE_VOICES.get(voice_var.get(), AVAILABLE_VOICES[voice_names[0]])
            rate_val = int(speed_slider.get())
            rate_str = f"+{rate_val}%" if rate_val >= 0 else f"{rate_val}%"
            self.voice.set_voice(voice_id)
            self.voice.set_rate(rate_str)
            self.brain.memory.set_pref("voice", voice_id)
            self.brain.memory.set_pref("voice_rate", rate_str)

            # Save theme
            selected_theme = theme_var.get()
            old_theme = self.brain.memory.get_pref("theme", "arc_reactor")
            self.brain.memory.set_pref("theme", selected_theme)

            if selected_theme != old_theme:
                self._append_msg(None, f"Theme changed to {THEMES[selected_theme]['name']}. Restart Jarvis to apply.", "system")

            self._append_msg(None, "Settings saved.", "system")
            on_close()

        ctk.CTkButton(
            win, text="Save Settings", font=("Segoe UI", 14, "bold"),
            fg_color=C["accent_dim"], hover_color=C["accent"],
            corner_radius=10, height=40, command=save_settings,
        ).pack(fill="x", padx=20, pady=(10, 18))

    # ══════════════════════════════════════════
    #  Cleanup
    # ══════════════════════════════════════════

    def _on_close(self):
        self.voice.stop_speaking()
        self.voice.stop_always_listening() if self._wake_on else None
        self.voice.cleanup()
        self.brain.cleanup()
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        if self._hotkey_registered:
            try:
                kb_lib.unhook_all()
            except Exception:
                pass
        self.root.destroy()
