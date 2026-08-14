"""
Jarvis Voice Engine
───────────────────
Edge TTS (neural voice) + Speech Recognition + SAPI fallback.
All public methods are thread-safe.
"""

import asyncio
import os
import tempfile
import threading
import time
import speech_recognition as sr

# ── Optional imports with graceful fallback ──
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("[!] edge-tts not installed. Run: pip install edge-tts")

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("[!] pygame not installed. Run: pip install pygame")

try:
    import win32com.client
    SAPI_AVAILABLE = True
except ImportError:
    SAPI_AVAILABLE = False

from config import VOICE_NAME, VOICE_RATE, VOICE_VOLUME, AVAILABLE_VOICES


class VoiceEngine:
    """Handles text-to-speech (Edge TTS / SAPI) and speech-to-text."""

    def __init__(self, on_state_change=None):
        """
        Args:
            on_state_change: Optional callback(state_str) called when voice
                             state changes. Must be thread-safe (use a queue).
        """
        self._speaking = False
        self._listening = False
        self._stop_flag = False
        self.on_state_change = on_state_change
        self._temp_dir = tempfile.gettempdir()
        self._mixer_ready = False
        self._mixer_lock = threading.Lock()
        self._init_mixer()
        self._current_voice = VOICE_NAME
        self._current_rate = VOICE_RATE

    # ──────────────────────────────────────────
    #  Pygame mixer
    # ──────────────────────────────────────────

    def _init_mixer(self):
        """Initialize pygame mixer once."""
        if PYGAME_AVAILABLE and not self._mixer_ready:
            try:
                pygame.mixer.init(frequency=24000, size=-16, channels=1, buffer=2048)
                self._mixer_ready = True
            except Exception as e:
                print(f"[Mixer Init Error] {e}")

    def cleanup(self):
        """Release audio resources. Call on app exit."""
        if self._mixer_ready:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception:
                pass

    # ──────────────────────────────────────────
    #  Text-to-Speech
    # ──────────────────────────────────────────

    def speak(self, text, on_complete=None):
        """Speak *text* in a background thread. Non-blocking.

        Args:
            text: String to speak.
            on_complete: Optional callback() invoked after speech ends.
        """
        t = threading.Thread(
            target=self._speak_worker,
            args=(text, on_complete),
            daemon=True,
        )
        t.start()

    def _speak_worker(self, text, on_complete):
        self._speaking = True
        self._stop_flag = False
        self._notify("speaking")

        try:
            if EDGE_TTS_AVAILABLE and PYGAME_AVAILABLE and self._mixer_ready:
                self._edge_speak(text)
            elif SAPI_AVAILABLE:
                self._sapi_speak(text)
            else:
                print(f"[No TTS available] {text}")
        except Exception as e:
            print(f"[Edge TTS Error] {e}  — falling back to SAPI")
            if SAPI_AVAILABLE:
                try:
                    self._sapi_speak(text)
                except Exception as e2:
                    print(f"[SAPI Fallback Error] {e2}")
        finally:
            self._speaking = False
            self._notify("idle")
            if on_complete:
                on_complete()

    def _edge_speak(self, text):
        """Generate speech with Edge TTS and play via pygame."""
        temp_file = os.path.join(self._temp_dir, "jarvis_tts_output.mp3")

        # ── Generate MP3 ──
        async def _generate():
            comm = edge_tts.Communicate(
                text=text,
                voice=self._current_voice,
                rate=self._current_rate,
                volume=VOICE_VOLUME,
            )
            await comm.save(temp_file)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_generate())
        finally:
            loop.close()

        # ── Playback ──
        with self._mixer_lock:
            try:
                pygame.mixer.music.load(temp_file)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    if self._stop_flag:
                        pygame.mixer.music.stop()
                        break
                    time.sleep(0.1)
            finally:
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pygame.mixer.music.stop()
                time.sleep(0.15)  # small delay to release file handle
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    def _sapi_speak(self, text):
        """Fallback: Windows SAPI voice (robotic but offline)."""
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak(text)

    def stop_speaking(self):
        """Interrupt current speech playback."""
        self._stop_flag = True
        if self._mixer_ready:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    # ──────────────────────────────────────────
    #  Speech-to-Text
    # ──────────────────────────────────────────

    def listen(self, timeout=8, phrase_time_limit=15):
        """Block and listen via microphone. Returns recognized text or None."""
        self._listening = True
        self._notify("listening")

        recognizer = sr.Recognizer()
        result = None

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                try:
                    audio = recognizer.listen(
                        source, timeout=timeout, phrase_time_limit=phrase_time_limit
                    )
                except sr.WaitTimeoutError:
                    return None

                self._notify("processing")
                try:
                    result = recognizer.recognize_google(audio, language="en-in")
                except sr.UnknownValueError:
                    return None
                except sr.RequestError as e:
                    print(f"[Speech API Error] {e}")
                    return None
        finally:
            self._listening = False

        return result

    # ──────────────────────────────────────────
    #  Properties
    # ──────────────────────────────────────────

    @property
    def is_speaking(self):
        return self._speaking

    @property
    def is_listening(self):
        return self._listening

    # ──────────────────────────────────────────
    #  Voice Settings
    # ──────────────────────────────────────────

    def set_voice(self, voice_name):
        """Change the TTS voice at runtime."""
        self._current_voice = voice_name

    def set_rate(self, rate_str):
        """Change the TTS speed at runtime. e.g. '+0%', '-10%', '+20%'"""
        self._current_rate = rate_str

    def get_current_voice(self):
        return self._current_voice

    def get_current_rate(self):
        return self._current_rate

    def preview_voice(self, voice_name, rate="-5%"):
        """Speak a sample with a specific voice (for settings preview)."""
        old_voice = self._current_voice
        old_rate = self._current_rate
        self._current_voice = voice_name
        self._current_rate = rate
        self.speak("Good evening sir. All systems operational and ready for your command.")
        # Restore after preview starts (speak is async)
        import time
        time.sleep(0.3)
        # Don't restore - let user hear the preview voice

    # ──────────────────────────────────────────
    #  Always-Listening (Wake Word)
    # ──────────────────────────────────────────

    def start_always_listening(self, keyword="jarvis", on_wake=None,
                                listen_timeout=3, pause=0.3):
        """Start background thread that listens for a keyword.

        Args:
            keyword: Word to listen for (case-insensitive).
            on_wake: callback() invoked when keyword is detected.
            listen_timeout: Seconds per listening burst.
            pause: Seconds to pause between bursts.
        """
        self._wake_keyword = keyword.lower()
        self._on_wake = on_wake
        self._wake_timeout = listen_timeout
        self._wake_pause = pause
        self._wake_active = True

        self._wake_thread = threading.Thread(
            target=self._wake_loop, daemon=True
        )
        self._wake_thread.start()

    def stop_always_listening(self):
        """Stop the always-listening background thread."""
        self._wake_active = False

    @property
    def is_always_listening(self):
        return getattr(self, "_wake_active", False)

    def _wake_loop(self):
        """Background loop: short listening bursts checking for keyword."""
        recognizer = sr.Recognizer()

        while self._wake_active:
            # Don't listen while Jarvis is speaking or actively processing
            if self._speaking or self._listening:
                time.sleep(0.5)
                continue

            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    try:
                        audio = recognizer.listen(
                            source,
                            timeout=self._wake_timeout,
                            phrase_time_limit=4,
                        )
                    except sr.WaitTimeoutError:
                        continue

                    try:
                        text = recognizer.recognize_google(
                            audio, language="en-in"
                        )
                        if self._wake_keyword in text.lower():
                            print(f"[Wake Word] Detected: '{text}'")
                            if self._on_wake:
                                self._on_wake()
                    except (sr.UnknownValueError, sr.RequestError):
                        pass

            except Exception as e:
                print(f"[Wake Loop Error] {e}")
                time.sleep(1)

            time.sleep(self._wake_pause)

    # ──────────────────────────────────────────
    #  Internal
    # ──────────────────────────────────────────

    def _notify(self, state):
        if self.on_state_change:
            try:
                self.on_state_change(state)
            except Exception:
                pass
