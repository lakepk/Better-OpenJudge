"""
OpenJudge Desktop Application

A thin native-window wrapper around the deployed web frontend.
All backend logic (database, judge, auth) runs on the server.

Usage:
    python desktop.py
    pyinstaller --onefile --windowed --name OpenJudge desktop.py
"""

import webview

# ── Configuration ───────────────────────────────────────────────
SERVER_URL = 'https://24.199.100.61/openjudge/'

if __name__ == '__main__':
    webview.create_window(
        title='OpenJudge',
        url=SERVER_URL,
        width=1200,
        height=800,
        min_size=(800, 600),
        text_select=True,
    )
    webview.start()
