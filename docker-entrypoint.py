#!/usr/bin/env python3
"""
Docker Entry Point for Gmail Attachment Watcher
Interactive setup for non-technical users
"""

import os
import sys
import time
from pathlib import Path
import getpass

# Add src to path
sys.path.append('/app/src')
sys.path.append('/app/config')

def print_banner():
    """Print welcome banner"""
    print("=" * 60)
    print("📧 GMAIL ATTACHMENT WATCHER")
    print("=" * 60)
    print("Welcome! This tool will monitor your Gmail for attachments")
    print("and automatically generate AI summaries for PDF documents.")
    print("=" * 60)
    print()

def get_user_input():
    """Get user credentials and preferences interactively"""
    print("🔧 SETUP CONFIGURATION")
    print("-" * 30)
    
    # Gmail credentials
    print("\n📧 Gmail Setup:")
    print("Note: You need to use an App Password, not your regular password.")
    print("Go to: Google Account > Security > 2-Step Verification > App Passwords")
    print()
    
    while True:
        gmail_address = input("Enter your Gmail address: ").strip()
        if "@gmail.com" in gmail_address:
            break
        print("❌ Please enter a valid Gmail address (must contain @gmail.com)")
    
    while True:
        gmail_password = getpass.getpass("Enter your Gmail App Password: ").strip()
        if len(gmail_password) > 0:
            break
        print("❌ Password cannot be empty")
    
    # Summary preferences
    print("\n📄 Summary Settings:")
    print("🤖 AI summarization available (CPU-only for Docker compatibility)")
    
    enable_summary = input("Enable PDF summarization? (y/n) [y]: ").strip().lower()
    enable_summary = enable_summary != 'n'
    
    if enable_summary:
        print("\nChoose summarization model:")
        print("1. Fast (t5-small) - Recommended for Docker, faster processing")
        print("2. Standard (facebook/bart-large-cnn) - Better quality, slower")
        model_choice = input("Select model (1/2) [1]: ").strip()
        
        if model_choice == '2':
            model = 'facebook/bart-large-cnn'
            print("✅ Using standard model (facebook/bart-large-cnn)")
            print("⚠️  Note: This may take longer to download and process")
        else:
            model = 't5-small'
            print("✅ Using fast model (t5-small) - Optimized for Docker")
    else:
        model = 't5-small'
        print("✅ PDF summarization disabled")
    
    print("\n📁 Storage:")
    print("Attachments will be saved to: /app/attachments")
    print("This folder is mounted to your host system.")
    
    return {
        'gmail_address': gmail_address,
        'gmail_password': gmail_password,
        'enable_summary': enable_summary,
        'model': model
    }

def create_config(settings):
    """Create configuration for the application"""
    # Set environment variables
    os.environ['GMAIL_ADDRESS'] = settings['gmail_address']
    os.environ['GMAIL_PASSWORD'] = settings['gmail_password']
    os.environ['ENABLE_SUMMARIZATION'] = 'true' if settings['enable_summary'] else 'false'
    os.environ['SUMMARIZATION_MODEL'] = settings['model']
    os.environ['ATTACHMENTS_DIR'] = '/app/attachments'
    os.environ['LOG_DIR'] = '/tmp'  # Logs to temp, not persistent
    os.environ['FORCE_CPU'] = 'true'  # Force CPU for Docker compatibility

def test_connection():
    """Test Gmail connection"""
    print("\n🔍 TESTING CONNECTION")
    print("-" * 30)
    
    try:
        from config import Config
        from gmail_watcher import GmailAttachmentWatcher
        
        print("⏳ Testing Gmail connection...")
        
        config = Config()
        watcher = GmailAttachmentWatcher(config, docker_mode=True)
        
        if watcher._connect_gmail():
            print("✅ Gmail connection successful!")
            watcher.mail.logout()
            return True
        else:
            print("❌ Gmail connection failed!")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

def start_monitoring():
    """Start the main monitoring application"""
    print("\n🚀 STARTING GMAIL MONITORING")
    print("-" * 30)
    print("✅ Configuration complete!")
    print("📧 Monitoring your Gmail for new attachments...")
    print("📄 PDF summaries will be generated automatically")
    print("📁 Files saved to: /app/attachments")
    print()
    print("💡 Tips:")
    print("   - Send yourself an email with a PDF to test")
    print("   - Press Ctrl+C to stop monitoring")
    print("   - Check /app/attachments for downloaded files")
    print()
    print("=" * 60)
    
    try:
        from config import Config
        from gmail_watcher import GmailAttachmentWatcher
        
        config = Config()
        watcher = GmailAttachmentWatcher(config, docker_mode=True)
        watcher.start()
        
    except KeyboardInterrupt:
        print("\n\n👋 Gmail monitoring stopped by user")
        print("Thank you for using Gmail Attachment Watcher!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Please check your configuration and try again.")

def main():
    """Main entry point"""
    print_banner()
    
    # Get user configuration
    settings = get_user_input()
    
    # Create configuration
    create_config(settings)
    
    # Test connection
    if not test_connection():
        print("\n❌ Setup failed! Please check your credentials.")
        print("\nCommon issues:")
        print("1. Make sure you're using an App Password, not regular password")
        print("2. Enable 2-Factor Authentication on your Google account")
        print("3. Generate App Password: Google Account > Security > App Passwords")
        sys.exit(1)
    
    # Start monitoring
    start_monitoring()

if __name__ == "__main__":
    main()
