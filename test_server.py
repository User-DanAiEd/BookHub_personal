#!/usr/bin/env python3
"""
Test script to run the BookHub Flask server for testing purposes.
"""

import sys
import os
import webbrowser
import threading

# Add the server directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from server.app import app

def open_browser():
    """Defines the path to Google Chrome and opens the server URL."""
    url = "http://127.0.0.1:3000"
    chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
    webbrowser.get(chrome_path).open(url)

    chrome_paths = [
        "C:/Program Files/Google/Chrome/Application/chrome.exe %s",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe %s"
    ]

    for path in chrome_paths:
        try:
            # Try launching with the specific path
            webbrowser.get(path).open(url)
            return
        except Exception:
            continue

    # Fallback if specific paths fail: try the universal browser launcher name
    try:
        webbrowser.get('chrome').open(url)
    except Exception:
        # Final fallback: open whatever your system default is
        webbrowser.open(url)

if __name__ == '__main__':
    print("Starting BookHub test server on http://127.0.0.1:3000")
    print("Press Ctrl+C to stop the server")
    threading.Timer(1.0, open_browser).start()  # Open the browser after a short delay 
    app.run(host='127.0.0.1', port=3000, debug=True, use_reloader=False)
