#!/usr/bin/env python3
"""
Test script to run the BookHub Flask server for testing purposes.
"""

import sys
import os

# Add the server directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from server.app import app

if __name__ == '__main__':
    print("Starting BookHub test server on http://127.0.0.1:3000")
    print("Press Ctrl+C to stop the server")
    app.run(host='127.0.0.1', port=3000, debug=True)
