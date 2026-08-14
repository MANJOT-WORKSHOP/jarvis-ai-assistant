"""
Jarvis Sound Effects
────────────────────
Programmatically generated sci-fi sounds.
Plays via pygame mixer (concurrent with TTS).
"""

import math
import struct

_sounds = {}
_ready = False


def _tone(freq, duration_ms, volume=0.3, fade_ms=10, sample_rate=24000):
    """Generate a sine wave tone as raw signed-16-bit PCM bytes."""
    n = int(sample_rate * duration_ms / 1000)
    fade_n = int(sample_rate * fade_ms / 1000)
    data = bytearray()
    for i in range(n):
        # Smooth fade in/out to avoid clicks
        if i < fade_n:
            env = i / fade_n
        elif i > n - fade_n:
            env = (n - i) / fade_n
        else:
            env = 1.0
        sample = int(volume * env * 32767 * math.sin(2 * math.pi * freq * i / sample_rate))
        data += struct.pack('<h', max(-32768, min(32767, sample)))
    return bytes(data)


def _silence(duration_ms, sample_rate=24000):
    """Generate silence."""
    n = int(sample_rate * duration_ms / 1000)
    return b'\x00\x00' * n


def _init():
    """Generate all sounds. Call after pygame.mixer.init()."""
    global _sounds, _ready
    if _ready:
        return True
    try:
        import pygame
        if not pygame.mixer.get_init():
            return False

        # ── Boot: ascending three-note chime (C5 → E5 → G5) ──
        boot = (
            _tone(523, 80, 0.15) + _silence(30) +
            _tone(659, 80, 0.18) + _silence(30) +
            _tone(784, 140, 0.22)
        )
        _sounds["boot"] = pygame.mixer.Sound(buffer=boot)

        # ── Listen: soft high double-beep ──
        listen = _tone(880, 60, 0.12) + _silence(40) + _tone(1047, 80, 0.15)
        _sounds["listen"] = pygame.mixer.Sound(buffer=listen)

        # ── Complete: pleasant major-third chime (C5 → E5) ──
        complete = _tone(523, 70, 0.12) + _silence(20) + _tone(659, 110, 0.16)
        _sounds["complete"] = pygame.mixer.Sound(buffer=complete)

        # ── Tick: ultra-short click (for boot steps) ──
        _sounds["tick"] = pygame.mixer.Sound(buffer=_tone(1200, 20, 0.08))

        # ── Error: low descending tone ──
        error = _tone(330, 120, 0.18) + _silence(20) + _tone(220, 180, 0.2)
        _sounds["error"] = pygame.mixer.Sound(buffer=error)

        # ── Startup: longer ascending sequence ──
        startup = (
            _tone(330, 60, 0.10) + _silence(20) +
            _tone(440, 60, 0.12) + _silence(20) +
            _tone(554, 60, 0.14) + _silence(20) +
            _tone(659, 70, 0.16) + _silence(20) +
            _tone(784, 90, 0.18) + _silence(20) +
            _tone(1047, 150, 0.22)
        )
        _sounds["startup"] = pygame.mixer.Sound(buffer=startup)

        _ready = True
        return True
    except Exception as e:
        print(f"[Sounds] Init failed: {e}")
        return False


def play(name):
    """Play a named sound effect. Non-blocking."""
    if not _ready:
        if not _init():
            return
    sound = _sounds.get(name)
    if sound:
        try:
            sound.play()
        except Exception:
            pass
