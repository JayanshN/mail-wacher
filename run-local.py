#!/usr/bin/env python3
"""
Local runner for Gmail Attachment Watcher
Run this script to start the watcher in your local development environment.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Import and run the main application
from gmail_watcher import main

if __name__ == "__main__":
    print("🚀 Starting Gmail Attachment Watcher (Local Mode)")
    print("=" * 50)
    
    # Check for .env file
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists():
        print("❌ .env file not found!")
        print("Please create .env file from config/.env.example")
        print("\nRun: cp config/.env.example .env")
        print("Then edit .env with your Gmail credentials")
        sys.exit(1)
    
    print("✅ Configuration loaded")
    print("✅ Starting Gmail monitoring...")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Gmail watcher stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)