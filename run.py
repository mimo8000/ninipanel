#!/usr/bin/env python3
"""
NiniPanel - VPN Management Panel
Run this script to start the panel
"""
import os
import sys
import subprocess
import threading

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_web():
    from web.app import app, init_db
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)

def run_bot():
    from bot.bot import main
    main()

if __name__ == '__main__':
    print("=" * 50)
    print("🛡️  NiniPanel v1.0.0")
    print("=" * 50)
    print()
    print("🌐 Web Panel: http://localhost:5000")
    print("🤖 Telegram Bot: Starting...")
    print()

    # Start web in thread
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()

    # Start bot (blocking)
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
