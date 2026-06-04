"""
Production entry point for gunicorn.

Usage:
    gunicorn -b 0.0.0.0:8080 web.run:app

Local development:
    python web/run.py
"""
import os
import sys

# ── Path setup ──────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)          # "from web.bridge …"  "from app …"
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'data'))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'judge'))

# ── Install bridge BEFORE importing Flask app ───────────────
# This patches database.create_submission so every submission
# automatically triggers a background judge thread.
from .bridge import install
install()

# ── Import Flask app ────────────────────────────────────────
# Imported via sys.path (data/ was added above).
# Now app.py's  from database import *  sees the patched version.
from data.app import app as flask_app

# ── Production config overrides ─────────────────────────────
flask_app.config['DEBUG'] = False

app = flask_app

# ── Local dev server ────────────────────────────────────────
if __name__ == '__main__':
    print("[web.run] Bridge installed, starting dev server on :8080 …")
    flask_app.run(host='0.0.0.0', port=8080, debug=True)
