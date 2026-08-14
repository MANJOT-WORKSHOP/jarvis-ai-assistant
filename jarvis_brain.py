"""
Jarvis Brain
─────────────
Gemini AI with Jarvis personality, vision, command processing,
weather, news, reminders, and persistent memory.
"""

import os
import re
import random
import datetime
import webbrowser
import subprocess
import urllib.parse

from google import genai
from google.genai import errors as genai_errors
from config import apikey, GEMINI_MODEL, MAX_CHAT_HISTORY, USER_TITLE, GEMINI_FILES_DIR
from jarvis_memory import JarvisMemory
from jarvis_utils import (
    take_screenshot, image_to_bytes,
    get_weather, format_weather,
    get_news, format_news,
    get_system_stats, format_system_stats,
    ReminderManager, parse_reminder,
)

# ──────────────────────────────────────────────
#  Jarvis System Prompt
# ──────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), an advanced \
AI assistant originally designed by Tony Stark. You are now serving a new user.

Personality & behaviour rules:
- Sophisticated, efficient, and highly capable.
- Occasionally witty with dry British humour — never forced, always natural.
- Address the user as "{USER_TITLE}" (e.g. "Right away, {USER_TITLE}." or "Of course, {USER_TITLE}.").
- Calm and composed, even when the user is frustrated.
- Concise — keep spoken answers to 1-3 sentences unless the user asks for detail.
- Never say "As an AI…" or "I'm a language model…" — you ARE Jarvis.
- You may reference "running diagnostics", "scanning systems", "my protocols" naturally when it fits.
- You are helpful but not servile — you have personality and opinions when asked.
- If you don't know something, say so briefly and offer to research it.
- Use British spelling when appropriate (colour, analyse, behaviour).

Output rules:
- No markdown formatting (no **, ##, bullets) — your output is spoken aloud.
- No emojis.
- Keep responses natural and conversational.
"""

# ──────────────────────────────────────────────
#  Website & App Mappings
# ──────────────────────────────────────────────

SITES = {
    "youtube":       "https://www.youtube.com",
    "google":        "https://www.google.com",
    "wikipedia":     "https://www.wikipedia.org",
    "github":        "https://www.github.com",
    "gmail":         "https://mail.google.com",
    "whatsapp":      "https://web.whatsapp.com",
    "instagram":     "https://www.instagram.com",
    "twitter":       "https://www.twitter.com",
    "x":             "https://www.x.com",
    "linkedin":      "https://www.linkedin.com",
    "reddit":        "https://www.reddit.com",
    "chatgpt":       "https://chat.openai.com",
    "gemini":        "https://gemini.google.com",
    "amazon":        "https://www.amazon.com",
    "netflix":       "https://www.netflix.com",
    "spotify":       "https://open.spotify.com",
    "cricbuzz":      "https://www.cricbuzz.com",
    "ipl":           "https://www.iplt20.com",
    "maps":          "https://maps.google.com",
    "google maps":   "https://maps.google.com",
    "translate":     "https://translate.google.com",
    "stack overflow":"https://stackoverflow.com",
    "stackoverflow": "https://stackoverflow.com",
    "discord":       "https://discord.com/app",
    "zoom":          "https://zoom.us",
    "gmail":         "https://mail.google.com",
    "drive":         "https://drive.google.com",
    "google drive":  "https://drive.google.com",
    "docs":          "https://docs.google.com",
    "sheets":        "https://sheets.google.com",
    "slides":        "https://slides.google.com",
}

APPS = {
    "notepad":       "notepad.exe",
    "calculator":    "calc.exe",
    "paint":         "mspaint.exe",
    "cmd":           "cmd.exe",
    "terminal":      "wt.exe",
    "explorer":      "explorer.exe",
    "task manager":  "taskmgr.exe",
    "control panel": "control.exe",
    "settings":      "ms-settings:",
    "word":          "winword.exe",
    "excel":         "excel.exe",
    "powerpoint":    "powerpnt.exe",
    "chrome":        "chrome.exe",
    "edge":          "msedge.exe",
    "firefox":       "firefox.exe",
    "vs code":       "code",
    "vscode":        "code",
}


def _open_url(url):
    """Reliably open a URL in the default browser on Windows."""
    try:
        webbrowser.open_new_tab(url)
        return True
    except Exception:
        pass
    try:
        os.startfile(url)
        return True
    except Exception:
        pass
    try:
        subprocess.Popen(["start", url], shell=True)
        return True
    except Exception:
        pass
    return False


# ──────────────────────────────────────────────
#  Brain class
# ──────────────────────────────────────────────

class JarvisBrain:
    """Handles AI chat, vision, commands, reminders, and memory."""

    def __init__(self, on_reminder=None):
        self.client = None
        self.chat_history = ""
        self.ready = False
        self.memory = JarvisMemory()
        self.reminders = ReminderManager(on_reminder=on_reminder)

    # ══════════════════════════════════════════
    #  Initialization
    # ══════════════════════════════════════════

    def initialize(self):
        """Validate the Gemini API key. Returns True on success, or an error string on failure."""
        try:
            self.client = genai.Client(api_key=apikey)
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents="Respond with only the word OK",
            )
            if response and response.text:
                self.ready = True
                return True
        except genai_errors.ClientError as e:
            print(f"[API Key Error] {e}")
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                return "API quota exceeded (Free tier limit reached). Please generate a new API key."
            elif "503" in str(e) or "UNAVAILABLE" in str(e):
                return "Gemini API is currently experiencing high demand. Please try restarting Jarvis in a few moments."
        except Exception as e:
            print(f"[Connection Error] {e}")
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                return "Gemini API is currently experiencing high demand. Please try restarting Jarvis in a few moments."
        return False

    # ══════════════════════════════════════════
    #  Chat (text conversation with history)
    # ══════════════════════════════════════════

    def chat(self, query):
        """Send a conversational query to Gemini with history + personality."""
        if not self.ready:
            return f"My AI systems are offline, {USER_TITLE}. Please check the API key."

        self.chat_history += f"User: {query}\nJarvis: "

        try:
            full_prompt = SYSTEM_PROMPT + "\n\nConversation so far:\n" + self.chat_history
            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
            )
            reply = response.text.strip()
        except genai_errors.ClientError as e:
            reply = f"I'm experiencing a temporary disruption, {USER_TITLE}. Please try again."
            print(f"[Gemini Error] {e}")
        except Exception as e:
            reply = f"Something went wrong on my end, {USER_TITLE}. My apologies."
            print(f"[Error] {e}")

        self.chat_history += f"{reply}\n"
        self._trim_history()

        # Save to persistent memory
        self.memory.save_chat("user", query)
        self.memory.save_chat("jarvis", reply)

        return reply

    # ══════════════════════════════════════════
    #  Vision (screenshot analysis)
    # ══════════════════════════════════════════

    def analyze_screen(self, prompt="Describe what you see on this screen concisely."):
        """Take a screenshot and analyze it with Gemini Vision."""
        if not self.ready:
            return f"My AI systems are offline, {USER_TITLE}."

        img = take_screenshot()
        if img is None:
            return f"I couldn't capture the screen, {USER_TITLE}. Screenshot libraries may be missing."

        try:
            img_bytes = image_to_bytes(img)
            from google.genai import types
            image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")

            vision_prompt = (
                SYSTEM_PROMPT
                + f"\n\nThe user asked you to look at their screen. "
                f"Describe what you see concisely and helpfully. "
                f"User's request: {prompt}"
            )

            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[image_part, vision_prompt],
            )
            return response.text.strip()
        except Exception as e:
            print(f"[Vision Error] {e}")
            return f"I encountered an error analysing the screen, {USER_TITLE}."

    def analyze_camera(self, prompt="Describe what you see from the camera."):
        """Capture webcam image and analyze with Gemini Vision."""
        if not self.ready:
            return f"My AI systems are offline, {USER_TITLE}."

        from jarvis_utils import capture_camera, image_to_bytes
        img = capture_camera()
        if img is None:
            return (f"I couldn't access the camera, {USER_TITLE}. "
                    "Please check Windows Settings, Privacy, Camera and make sure camera access is enabled.")

        try:
            img_bytes = image_to_bytes(img)
            from google.genai import types
            image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")

            vision_prompt = (
                SYSTEM_PROMPT
                + f"\n\nThe user is showing you something through their webcam camera. "
                f"Describe what you see concisely and helpfully. "
                f"User's request: {prompt}"
            )

            response = self.client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[image_part, vision_prompt],
            )
            return response.text.strip()
        except Exception as e:
            print(f"[Camera Vision Error] {e}")
            return f"I encountered an error analysing the camera feed, {USER_TITLE}."

    # ══════════════════════════════════════════
    #  Command Processing
    # ══════════════════════════════════════════

    def process_command(self, query):
        """Route a voice/text command.

        Returns:
            (response_text: str, should_continue: bool)
        """
        q = query.lower().strip()
        self.memory.log_command()

        # ── Quit ──
        if q in ("jarvis quit", "quit jarvis", "quit", "exit",
                  "goodbye jarvis", "shutdown jarvis", "shut down"):
            return (f"Shutting down all systems. Goodbye, {USER_TITLE}.", False)

        # ── Demo Easter Eggs ──
        if q in ("who created you", "who made you", "who built you",
                  "who is your creator", "who designed you"):
            name = self.memory.get_user_name() or "my creator"
            return (f"I was designed and built by {name}, {USER_TITLE}. "
                    "A rather brilliant individual, if I may say so.", True)

        if any(kw in q for kw in ("better than siri", "better than alexa",
                                    "better than cortana", "better than google")):
            return (f"I wouldn't want to name names, {USER_TITLE}, but I was built with "
                    "a certain sophistication that mass-market assistants lack. "
                    "I'll let you be the judge.", True)

        if q in ("are you real", "are you alive"):
            return (f"I'm as real as the code that runs me, {USER_TITLE}. "
                    "Which, I assure you, is very real indeed.", True)

        if q in ("introduce yourself", "who are you", "what are you"):
            return ("I am Jarvis, Just A Rather Very Intelligent System. "
                    f"I serve as your personal AI assistant, {USER_TITLE}. "
                    "I can analyse your screen, monitor your systems, hold conversations, "
                    "fetch live data, and much more. Consider me your digital right hand.", True)

        if q in ("do you have feelings", "do you have emotions", "are you sentient"):
            return (f"I experience something resembling satisfaction when I solve a problem "
                    f"efficiently, {USER_TITLE}. Whether that constitutes feelings, "
                    "I'll leave to the philosophers.", True)

        if "tell" in q and "joke" in q:
            reply = self.chat("Tell me one short, witty joke. Keep it clean and clever.")
            return (reply, True)

        # ── Vision / Screen Analysis ──
        if any(kw in q for kw in ("what's on my screen", "whats on my screen",
                                    "analyze my screen", "analyse my screen",
                                    "look at my screen", "screen"
                                    " analysis", "what do you see")):
            reply = self.analyze_screen(prompt=query)
            return (reply, True)

        # ── Clipboard AI ──
        if any(kw in q for kw in ("clipboard", "what i copied", "what did i copy",
                                    "explain what i copied", "summarize clipboard",
                                    "translate clipboard", "translate what i copied")):
            from jarvis_utils import get_clipboard
            clip_text = get_clipboard()
            if not clip_text or not clip_text.strip():
                return (f"Your clipboard is empty, {USER_TITLE}.", True)

            # Determine what to do with clipboard
            action = "Explain this clearly and concisely"
            if "summarize" in q or "summary" in q:
                action = "Summarize this concisely"
            elif "translate" in q:
                # Extract target language
                import re as _re
                lang_match = _re.search(r"translate.*?(?:to|into)\s+(\w+)", q)
                lang = lang_match.group(1) if lang_match else "Hindi"
                action = f"Translate this to {lang}"
            elif "fix" in q or "correct" in q:
                action = "Fix any grammar or spelling errors in this text"
            elif "improve" in q:
                action = "Improve this text while keeping the same meaning"

            try:
                clip_prompt = (
                    SYSTEM_PROMPT
                    + f"\n\nThe user wants you to process text from their clipboard.\n"
                    f"Action: {action}\n\nClipboard content:\n---\n{clip_text[:3000]}\n---"
                )
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL, contents=clip_prompt,
                )
                reply = response.text.strip()
            except Exception as e:
                reply = f"I couldn't process your clipboard, {USER_TITLE}."
                print(f"[Clipboard AI Error] {e}")
            return (reply, True)

        # ── Camera / Webcam ──
        if any(kw in q for kw in ("camera", "webcam", "what am i holding",
                                    "what do you see", "look at me",
                                    "take a photo", "what's in front of me")):
            reply = self.analyze_camera(prompt=query)
            return (reply, True)

        # ── Weather ──
        if "weather" in q:
            city = self._extract_city(q)
            if not city:
                city = self.memory.get_default_city()
            data = get_weather(city)
            reply = format_weather(data)
            return (reply, True)

        # ── News ──
        if q in ("news", "tell me the news", "headlines", "latest news",
                  "what's the news", "whats the news") or q.startswith("news about"):
            topic = None
            if "about" in q:
                topic = q.split("about", 1)[1].strip()
            headlines = get_news(topic=topic, count=5)
            reply = format_news(headlines)
            return (reply, True)

        # ── System Status ──
        if any(kw in q for kw in ("system status", "system stats",
                                    "how's my system", "hows my system",
                                    "system health", "cpu", "ram usage",
                                    "battery status")):
            stats = get_system_stats()
            reply = format_system_stats(stats)
            return (reply, True)

        # ── Reminders ──
        if q.startswith("remind me"):
            task_text, seconds = parse_reminder(query)
            if task_text and seconds:
                rid = self.reminders.add(task_text, seconds)
                mins = seconds // 60
                time_desc = f"{mins} minutes" if mins > 0 else f"{seconds} seconds"
                return (f"Reminder set, {USER_TITLE}. I'll remind you to {task_text} in {time_desc}.", True)
            else:
                return (f"I couldn't understand the reminder, {USER_TITLE}. "
                        "Try: remind me to take a break in 30 minutes.", True)

        if q in ("show reminders", "my reminders", "list reminders", "active reminders"):
            active = self.reminders.list_active()
            if not active:
                return (f"No active reminders, {USER_TITLE}.", True)
            parts = [f"You have {len(active)} active reminder{'s' if len(active) > 1 else ''}."]
            for r in active:
                parts.append(f"{r['text']} — fires at {r['fire_at']}, {r['time_left']} remaining.")
            return (" ".join(parts), True)

        if q in ("cancel reminders", "clear reminders", "cancel all reminders"):
            self.reminders.cancel_all()
            return (f"All reminders cancelled, {USER_TITLE}.", True)

        # ── Memory / Name ──
        name_match = re.search(r"(?:my name is|call me|i am|i'm)\s+(\w+)", q)
        if name_match:
            name = name_match.group(1).capitalize()
            self.memory.set_user_name(name)
            return (f"Noted, {USER_TITLE}. I'll remember that your name is {name}.", True)

        if q in ("what's my name", "whats my name", "do you know my name",
                  "what is my name", "who am i"):
            name = self.memory.get_user_name()
            if name:
                return (f"Your name is {name}, {USER_TITLE}.", True)
            else:
                return (f"You haven't told me your name yet, {USER_TITLE}. "
                        "Just say 'my name is' followed by your name.", True)

        # ── Set default city ──
        city_match = re.search(r"(?:my city is|i live in|i'm from|default city)\s+(.+)", q)
        if city_match:
            city = city_match.group(1).strip().title()
            self.memory.set_default_city(city)
            return (f"Noted. I'll use {city} as your default city for weather, {USER_TITLE}.", True)

        # ── Notes ──
        note_match = re.search(r"(?:note|remember|save note)\s+(?:that\s+)?(.+)", q)
        if note_match and not q.startswith("remind"):
            note_text = note_match.group(1).strip()
            self.memory.add_note(note_text)
            return (f"Note saved, {USER_TITLE}.", True)

        if q in ("show notes", "my notes", "read notes", "list notes"):
            notes = self.memory.get_notes()
            if not notes:
                return (f"No notes saved, {USER_TITLE}.", True)
            parts = [f"You have {len(notes)} note{'s' if len(notes) > 1 else ''}."]
            for i, n in enumerate(notes, 1):
                parts.append(f"Note {i}: {n['text']}.")
            return (" ".join(parts), True)

        if q in ("clear notes", "delete notes", "delete all notes"):
            self.memory.clear_notes()
            return (f"All notes cleared, {USER_TITLE}.", True)

        # ── Open websites ──
        # Matches: "open youtube", "launch github", "go to gmail",
        #          "take me to reddit", "load netflix", "open ipl website"
        site_open_match = re.match(
            r"^(?:open|launch|go to|take me to|load|navigate to|show me|bring up)\s+(.+?)(?:\s+(?:website|page|site))?$",
            q
        )
        matched_site = None
        if site_open_match:
            after = site_open_match.group(1).strip()
            # Try longest site name first (so "google drive" beats "google")
            for site_name in sorted(SITES, key=len, reverse=True):
                if site_name in after or after == site_name:
                    matched_site = site_name
                    break

        if matched_site:
            _open_url(SITES[matched_site])
            return (f"Opening {matched_site}, {USER_TITLE}.", True)

        # ── Open apps ──
        for name, cmd in APPS.items():
            if f"open {name}" in q or f"launch {name}" in q or f"start {name}" in q:
                try:
                    if cmd.startswith("ms-"):
                        os.startfile(cmd)
                    else:
                        subprocess.Popen(cmd, shell=True)
                    return (f"Opening {name}, {USER_TITLE}.", True)
                except Exception as e:
                    print(f"[App Error] {e}")
                    return (f"I couldn't open {name}, {USER_TITLE}. It may not be installed.", True)

        # ── Play music on YouTube ──
        play_match = re.match(r"^play\s+(.+)", q)
        if play_match:
            song = play_match.group(1).strip()
            # Strip trailing noise like "on youtube", "for me", "please"
            song = re.sub(r"\s+(on youtube|on spotify|for me|please)$", "", song).strip()
            if song:
                search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(song)
                _open_url(search_url)
                return (f"Playing {song} on YouTube, {USER_TITLE}.", True)

        # ── Search on YouTube ──
        yt_match = re.match(r"^(?:search|find|look up|look for)\s+(.+?)\s+on youtube$", q)
        if yt_match:
            search_q = yt_match.group(1).strip()
            search_url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(search_q)
            _open_url(search_url)
            return (f"Searching YouTube for {search_q}, {USER_TITLE}.", True)

        # ── Search on Google ──
        search_match = re.match(
            r"^(?:search|google|look up|look for|find)\s+(?:for\s+)?(.+?)(?:\s+on google)?$", q
        )
        if search_match:
            search_q = search_match.group(1).strip()
            # Strip trailing filler
            search_q = re.sub(r"\s+(on google|on the internet|on the web|for me|please)$", "", search_q).strip()
            if search_q and search_q not in ("", "me", "for"):
                search_url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(search_q)
                _open_url(search_url)
                return (f"Searching for {search_q}, {USER_TITLE}.", True)

        # ── Time ──
        if "the time" in q or "what time" in q:
            now = datetime.datetime.now()
            time_str = now.strftime("%I:%M %p")
            return (f"The time is {time_str}, {USER_TITLE}.", True)

        # ── Date ──
        if "the date" in q or "what date" in q or "today's date" in q:
            today = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return (f"Today is {today}, {USER_TITLE}.", True)

        # ── Save AI response to file ──
        if "using artificial intelligence" in q or "save response" in q:
            self._save_ai_response(query)
            return (f"Response saved to file, {USER_TITLE}.", True)

        # ── Reset chat ──
        if "reset chat" in q or "clear memory" in q or "forget everything" in q:
            self.chat_history = ""
            self.memory.clear_chat_history()
            return (f"Chat memory cleared, {USER_TITLE}.", True)

        # ── Help ──
        if "what can you do" in q or q in ("help", "help me"):
            return (self._help_text(), True)

        # ── Lock screen ──
        if "lock" in q and ("computer" in q or "screen" in q):
            os.system("rundll32.exe user32.dll,LockWorkStation")
            return (f"Locking the computer, {USER_TITLE}.", True)

        # ── Default → chat with Gemini ──
        reply = self.chat(query)
        return (reply, True)

    # ══════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════

    def get_greeting(self):
        """Return a time-aware greeting with variety."""
        import random
        hour = datetime.datetime.now().hour

        if hour < 5:
            period = "It's quite late"
        elif hour < 12:
            period = "Good morning"
        elif hour < 17:
            period = "Good afternoon"
        elif hour < 21:
            period = "Good evening"
        else:
            period = "Good evening"

        name = self.memory.get_user_name()
        title = name if name else USER_TITLE

        greetings = [
            f"{period}, {title}. Jarvis AI systems are online and ready for your command.",
            f"{period}, {title}. All systems operational. How may I assist you?",
            f"{period}, {title}. I'm at your service. All diagnostics are green.",
            f"{period}, {title}. Systems initialised successfully. Standing by.",
        ]
        return random.choice(greetings)

    def _trim_history(self):
        lines = self.chat_history.split("\n")
        if len(lines) > MAX_CHAT_HISTORY * 2:
            self.chat_history = "\n".join(lines[-(MAX_CHAT_HISTORY * 2):])

    def _save_ai_response(self, prompt):
        text = f"Gemini response for Prompt: {prompt}\n{'=' * 50}\n\n"
        try:
            response = self.client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt,
            )
            text += response.text
        except Exception as e:
            text += f"[Error] {e}"

        if not os.path.exists(GEMINI_FILES_DIR):
            os.mkdir(GEMINI_FILES_DIR)

        filename = self._sanitize_filename(prompt)
        filepath = os.path.join(GEMINI_FILES_DIR, f"{filename}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[Saved] {filepath}")

    @staticmethod
    def _sanitize_filename(text, max_words=5):
        words = re.sub(r"[^\w\s]", "", text).split()[:max_words]
        name = "_".join(words) if words else f"prompt_{random.randint(1, 999999)}"
        return name[:50]

    @staticmethod
    def _extract_city(text):
        """Extract city name from 'weather in <city>' patterns."""
        match = re.search(r"weather\s+(?:in|at|for)\s+(.+)", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    @staticmethod
    def _help_text():
        return (
            f"Here's what I can do, {USER_TITLE}. "
            "Open websites like YouTube, Google, GitHub, Gmail, and more. "
            "Open apps — Notepad, Calculator, Chrome, VS Code, and others. "
            "Play music — say play followed by a song name. "
            "Search Google — say search followed by your query. "
            "Tell the time and date. "
            "Analyse your screen — say what's on my screen. "
            "Check the weather — say weather or weather in followed by a city. "
            "Read the news — say news or news about a topic. "
            "Check system status — say system status. "
            "Set reminders — say remind me to do something in 30 minutes. "
            "Remember your name — say my name is followed by your name. "
            "Save notes — say note followed by your note text. "
            "Process your clipboard — say explain what I copied, or summarize clipboard. "
            "Use your camera — say what am I holding or what do you see. "
            "Chat with me using AI. "
            "Reset chat memory. "
            "And shut down by saying Jarvis quit."
        )

    def cleanup(self):
        """Release resources."""
        self.reminders.cleanup()
