"""
OpenJudge Desktop Application

Usage:
    python desktop.py          # Run directly
    pyinstaller --onefile --windowed desktop.py   # Build .exe

Architecture:
    desktop.py → starts Flask on 127.0.0.1:4399 → PyWebView wraps it
    Zero changes to existing data/ judge/ web/ code.
"""

import os
import sys
import threading

# ── Path setup (mirrors web/run.py) ────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'data'))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'judge'))

# ── Install judge bridge BEFORE importing Flask app ────────────
from web.bridge import install


# ── Start Flask in background thread ───────────────────────────
def _start_flask():
    install()
    from data.app import app
    app.config['DEBUG'] = False
    app.run(host='127.0.0.1', port=4399, debug=False, use_reloader=False)


def main():
    t = threading.Thread(target=_start_flask, daemon=True, name='flask-server')
    t.start()

    import webview
    webview.create_window(
        title='OpenJudge',
        url='http://127.0.0.1:4399',
        width=1200,
        height=800,
        min_size=(800, 600),
        text_select=True,
    )
    webview.start()
    # webview.start() blocks — when user closes the window, the
    # daemon Flask thread exits automatically with the process.


if __name__ == '__main__':
    main()
