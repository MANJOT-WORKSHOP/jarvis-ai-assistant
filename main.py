"""
J.A.R.V.I.S  —  AI Assistant
─────────────────────────────
Entry point.  Launches the GUI dashboard.

Usage:
    python main.py
"""

from jarvis_gui import JarvisGUI


def main():
    print("=" * 50)
    print("       J.A.R.V.I.S  AI  ASSISTANT  v2.0")
    print("=" * 50)
    print("[*] Starting GUI…\n")

    app = JarvisGUI()
    app.run()

    print("\n[Jarvis offline]")


if __name__ == "__main__":
    main()