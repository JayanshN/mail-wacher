"""
Configuration settings for Gmail Attachment Watcher
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_env_path = Path(__file__).parent.parent / '.env'
if load_env_path.exists():
    load_dotenv(load_env_path)

class Config:
    """Configuration class for Gmail Attachment Watcher"""
    
    # Gmail credentials
    GMAIL_ADDRESS = os.getenv('GMAIL_ADDRESS')
    GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')  # Use App Password
    
    # Directories
    BASE_DIR = Path(__file__).parent.parent
    ATTACHMENTS_DIR = os.getenv('ATTACHMENTS_DIR', str(BASE_DIR / 'data' / 'attachments'))
    LOG_DIR = os.getenv('LOG_DIR', str(BASE_DIR / 'data' / 'logs'))
    
    # LLM Configuration
    ENABLE_SUMMARIZATION = os.getenv('ENABLE_SUMMARIZATION', 'true').lower() == 'true'
    SUMMARIZATION_MODEL = os.getenv('SUMMARIZATION_MODEL', 'facebook/bart-large-cnn')
    FALLBACK_SUMMARIZATION_MODEL = os.getenv('FALLBACK_SUMMARIZATION_MODEL', 't5-small')
    FORCE_CPU = os.getenv('FORCE_CPU', 'false').lower() == 'true'
    
    # Summarization parameters
    MAX_INPUT_LENGTH = int(os.getenv('MAX_INPUT_LENGTH', '1024'))
    SUMMARY_MAX_LENGTH = int(os.getenv('SUMMARY_MAX_LENGTH', '200'))
    SUMMARY_MIN_LENGTH = int(os.getenv('SUMMARY_MIN_LENGTH', '50'))
    
    # IMAP settings
    IMAP_SERVER = os.getenv('IMAP_SERVER', 'imap.gmail.com')
    IMAP_PORT = int(os.getenv('IMAP_PORT', '993'))
    
    # Monitoring settings
    RECONNECT_DELAY = int(os.getenv('RECONNECT_DELAY', '10'))
    MAX_RECONNECT_ATTEMPTS = int(os.getenv('MAX_RECONNECT_ATTEMPTS', '5'))
    
    # File processing
    MAX_ATTACHMENT_SIZE = int(os.getenv('MAX_ATTACHMENT_SIZE', '50')) * 1024 * 1024  # 50MB default
    ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', '.pdf,.doc,.docx,.txt,.xlsx,.png,.jpg,.jpeg').split(',')
    
    def validate(self):
        """Validate configuration settings"""
        errors = []
        
        if not self.GMAIL_ADDRESS:
            errors.append("GMAIL_ADDRESS is required")
        if not self.GMAIL_PASSWORD:
            errors.append("GMAIL_PASSWORD is required")
            
        # Create directories if they don't exist
        Path(self.ATTACHMENTS_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.LOG_DIR).mkdir(parents=True, exist_ok=True)
        
        if errors:
            raise ValueError("Configuration errors: " + ", ".join(errors))
        
        return True
    
    def __repr__(self):
        """String representation hiding sensitive data"""
        return f"Config(gmail={self.GMAIL_ADDRESS}, summarization={self.ENABLE_SUMMARIZATION})"