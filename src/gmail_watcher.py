#!/usr/bin/env python3
"""
Gmail Attachment Watcher with Local LLM Summarization
Monitors Gmail INBOX via IMAP IDLE for new emails with attachments.
Downloads attachments and generates AI summaries for PDFs.
"""

import os
import re
import time
import json
import logging
import imaplib
import email
from email.header import decode_header
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
import threading
import signal
import sys

# Add config path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'config'))
from config import Config

# PDF processing
try:
    import pdfplumber
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    print("Warning: PDF processing libraries not available. Install pdfplumber and PyPDF2.")
    PDF_AVAILABLE = False

# LLM for summarization
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
    LLM_AVAILABLE = True
except ImportError:
    print("INFO: AI summarization libraries not available. Attachment downloading will work, but PDF summarization will be disabled.")
    LLM_AVAILABLE = False

# Configure logging
def setup_logging(log_dir: Path):
    """Setup logging configuration"""
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'gmail_watcher.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )
    return logging.getLogger(__name__)

class GmailAttachmentWatcher:
    def __init__(self, config: Config, docker_mode: bool = False):
        self.config = config
        self.docker_mode = docker_mode
        
        # Setup logging
        if docker_mode:
            self.logger = self._setup_docker_logging()
        else:
            self.logger = setup_logging(Path(config.LOG_DIR))
        
        # Gmail IMAP settings
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        
        # Directories
        self.attachments_dir = Path(config.ATTACHMENTS_DIR)
        self.attachments_dir.mkdir(exist_ok=True)
        
        # IMAP connection
        self.mail = None
        self.running = True
        
        # Initialize summarizer
        self.summarizer = None
        if LLM_AVAILABLE and config.ENABLE_SUMMARIZATION:
            self._init_summarizer()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_docker_logging(self):
        """Setup simplified logging for Docker mode"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger(__name__)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.mail:
            try:
                self.mail.logout()
            except:
                pass
        sys.exit(0)
        
    def _init_summarizer(self):
        """Initialize the local LLM summarizer"""
        try:
            self.logger.info("Initializing local summarization model...")
            
            # Use model from config
            model_name = self.config.SUMMARIZATION_MODEL
            
            # Check if we should use CPU only
            device = 0 if torch.cuda.is_available() and not self.config.FORCE_CPU else -1
            
            self.summarizer = pipeline(
                "summarization",
                model=model_name,
                device=device,
                torch_dtype=torch.float32 if device == -1 else torch.float16
            )
            
            self.logger.info(f"Summarization model {model_name} loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize summarizer: {e}")
            # Try fallback model
            try:
                fallback_model = self.config.FALLBACK_SUMMARIZATION_MODEL
                self.logger.info(f"Trying fallback model: {fallback_model}")
                self.summarizer = pipeline(
                    "summarization",
                    model=fallback_model,
                    device=-1  # Force CPU for smaller model
                )
                self.logger.info("Fallback summarization model loaded")
            except Exception as e2:
                self.logger.error(f"Failed to load fallback model: {e2}")
                self.summarizer = None
    
    def _connect_gmail(self):
        """Connect to Gmail IMAP server"""
        try:
            if not self.config.GMAIL_ADDRESS or not self.config.GMAIL_PASSWORD:
                raise ValueError("Gmail credentials not found in configuration.")
            
            self.logger.info("Connecting to Gmail IMAP...")
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.mail.login(self.config.GMAIL_ADDRESS, self.config.GMAIL_PASSWORD)
            self.mail.select('INBOX')
            self.logger.info("Connected to Gmail successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Gmail: {e}")
            self.mail = None
            return False
    
    def _sanitize_filename(self, filename: str, sender: str, timestamp: str) -> str:
        """Create a sanitized filename with sender and timestamp"""
        # Extract email from sender (handle formats like "Name <email@domain.com>")
        email_match = re.search(r'<(.+?)>|([^\s<>]+@[^\s<>]+)', sender)
        if email_match:
            email_addr = email_match.group(1) or email_match.group(2)
        else:
            email_addr = sender
        
        # Clean sender email (remove @ and . for filename safety)
        clean_sender = re.sub(r'[<>@.]', '_', email_addr.lower())
        clean_sender = re.sub(r'[^\w\-_]', '', clean_sender)
        
        # Clean original filename
        name, ext = os.path.splitext(filename)
        clean_name = re.sub(r'[^\w\-_.]', '_', name)
        clean_ext = ext.lower()
        
        # Create unique filename
        unique_filename = f"{clean_sender}_{timestamp}_{clean_name}{clean_ext}"
        return unique_filename
    
    def _decode_header_value(self, header_value: str) -> str:
        """Decode email header values"""
        try:
            decoded_parts = decode_header(header_value)
            decoded_string = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
                else:
                    decoded_string += part
            return decoded_string
        except:
            return str(header_value)
    
    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF file"""
        if not PDF_AVAILABLE:
            return "PDF processing not available - install pdfplumber and PyPDF2"
        
        text = ""
        
        try:
            # Try pdfplumber first (better for complex layouts)
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            if text.strip():
                return text
                
        except Exception as e:
            self.logger.warning(f"pdfplumber failed for {pdf_path}: {e}")
        
        try:
            # Fallback to PyPDF2
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                    
        except Exception as e:
            self.logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
            
        return text
    
    def _summarize_text(self, text: str) -> str:
        """Generate document description using local LLM"""
        if not self.summarizer:
            return "Document analysis unavailable - LLM not initialized"
        
        try:
            # First try to create a smart description based on content analysis
            description = self._create_smart_description(text)
            if description:
                return description
                
            # Fallback to LLM if smart analysis doesn't work
            # Truncate text if too long (model token limits)
            max_input_length = self.config.MAX_INPUT_LENGTH
            if len(text.split()) > max_input_length:
                text = ' '.join(text.split()[:max_input_length])
            
            # Create a better prompt for document analysis
            analysis_prompt = f"""Analyze this document and describe what it is about in 2-3 sentences. Start with "This document is..." and explain:
1. What type of document it is
2. What it contains or certifies
3. Who it's for or its purpose

Document text: {text[:500]}...

Description:"""
            
            # Generate document description
            result = self.summarizer(
                analysis_prompt,
                max_length=100,
                min_length=30,
                do_sample=True,
                temperature=0.7,
                truncation=True
            )
            
            return result[0]['summary_text']
            
        except Exception as e:
            # Final fallback: Create a simple document analysis based on keywords
            return self._create_fallback_description(text)
    
    def _create_smart_description(self, text: str) -> str:
        """Create intelligent document description based on content analysis"""
        text_lower = text.lower()
        
        # AWS Certificate detection
        if "aws certified" in text_lower and "exam results" in text_lower:
            # Extract certification type
            cert_type = "AWS Certification"
            if "ai practitioner" in text_lower:
                cert_type = "AWS Certified AI Practitioner"
            elif "cloud practitioner" in text_lower:
                cert_type = "AWS Certified Cloud Practitioner"
            elif "solutions architect" in text_lower:
                cert_type = "AWS Certified Solutions Architect"
            
            # Extract candidate name and score
            candidate_name = ""
            score = ""
            status = "PASS" if "pass/fail: pass" in text_lower else "FAIL"
            
            # Try to extract candidate name
            if "candidate:" in text_lower:
                try:
                    candidate_line = [line for line in text.split('\n') if 'candidate:' in line.lower()][0]
                    candidate_name = candidate_line.split('candidate:')[1].split('exam date:')[0].strip()
                except:
                    pass
            
            # Try to extract score
            if "candidate score:" in text_lower:
                try:
                    score_line = [line for line in text.split('\n') if 'candidate score:' in line.lower()][0]
                    score = score_line.split('score:')[1].split('pass/fail:')[0].strip()
                except:
                    pass
            
            description = f"This document is an official {cert_type} exam results certificate. "
            if candidate_name:
                description += f"It certifies that {candidate_name} has successfully "
            else:
                description += "It certifies that the candidate has successfully "
            description += f"passed the AWS certification exam with a score of {score if score else 'above the required threshold'}. "
            description += "This document serves as proof of AWS cloud computing and AI/ML competency and can be used for professional validation."
            
            return description
        
        # Invoice/Bill detection
        elif any(word in text_lower for word in ["invoice", "bill", "amount due", "payment"]):
            return "This document is a financial invoice or billing statement containing payment details, amounts due, and transaction information for goods or services provided."
        
        # Contract/Agreement detection
        elif any(word in text_lower for word in ["agreement", "contract", "terms and conditions", "legal"]):
            return "This document is a legal agreement or contract outlining terms, conditions, and obligations between parties for a specific arrangement or transaction."
        
        # Manual/Guide detection
        elif any(word in text_lower for word in ["manual", "guide", "instructions", "how to", "step by step"]):
            return "This document is an instructional manual or guide providing step-by-step procedures, best practices, and detailed information for specific tasks or operations."
        
        # Report detection
        elif any(word in text_lower for word in ["report", "analysis", "findings", "results", "data"]):
            return "This document is an analytical report containing findings, data analysis, and insights on specific topics or business metrics for decision-making purposes."
        
        return None  # No smart description found
    
    def _create_fallback_description(self, text: str) -> str:
        """Create a simple document description when other methods fail"""
        text_lower = text.lower()
        
        # Document type detection with more specific descriptions
        if any(word in text_lower for word in ["certificate", "certification", "certified"]):
            doc_type = "professional certification document"
            purpose = "validating specific skills and competencies"
        elif any(word in text_lower for word in ["manual", "guide", "handbook", "instructions"]):
            doc_type = "instructional manual or guide"
            purpose = "providing step-by-step procedures and best practices"
        elif any(word in text_lower for word in ["report", "analysis", "findings"]):
            doc_type = "analytical report"
            purpose = "presenting data, findings, and insights"
        elif any(word in text_lower for word in ["invoice", "bill", "payment", "receipt"]):
            doc_type = "financial document"
            purpose = "recording payment information and transaction details"
        elif any(word in text_lower for word in ["contract", "agreement", "terms"]):
            doc_type = "legal agreement"
            purpose = "defining terms and obligations between parties"
        else:
            doc_type = "business document"
            purpose = "containing important information and data"
        
        # Extract key topics
        key_topics = []
        topic_keywords = {
            "aws": "AWS Cloud Services",
            "artificial intelligence": "Artificial Intelligence",
            "machine learning": "Machine Learning", 
            "ai": "AI Technology",
            "cloud": "Cloud Computing",
            "technology": "Technology",
            "business": "Business Operations",
            "finance": "Financial Management",
            "security": "Security & Compliance",
            "certification": "Professional Certification"
        }
        
        for keyword, topic in topic_keywords.items():
            if keyword in text_lower and topic not in key_topics:
                key_topics.append(topic)
        
        # Build comprehensive description
        description = f"This document is a {doc_type}"
        
        if key_topics:
            if len(key_topics) == 1:
                description += f" related to {key_topics[0]}"
            else:
                description += f" covering {', '.join(key_topics[:2])}"
                if len(key_topics) > 2:
                    description += f" and other related topics"
        
        description += f". It serves the purpose of {purpose}"
        
        # Add content context
        word_count = len(text.split())
        if word_count < 200:
            description += " and contains concise essential information"
        elif word_count < 1000:
            description += " and provides detailed information and guidelines"
        else:
            description += " and includes comprehensive details and extensive documentation"
        
        return description + "."
    
    def _process_attachment(self, attachment_data: bytes, filename: str, 
                          sender: str, subject: str, timestamp: str) -> Optional[Path]:
        """Save attachment and process if PDF"""
        try:
            # Create unique filename
            unique_filename = self._sanitize_filename(filename, sender, timestamp)
            file_path = self.attachments_dir / unique_filename
            
            # Save attachment
            with open(file_path, 'wb') as f:
                f.write(attachment_data)
            
            self.logger.info(f"Saved attachment: {unique_filename}")
            
            # Log attachment details
            attachment_info = {
                'timestamp': datetime.now().isoformat(),
                'sender': sender,
                'subject': subject,
                'original_filename': filename,
                'saved_filename': unique_filename,
                'file_size': len(attachment_data),
                'file_path': str(file_path)
            }
            
            # Log to console
            if self.docker_mode:
                self.logger.info(f"📎 Saved: {filename} ({len(attachment_data)} bytes) from {sender}")
            else:
                self.logger.info(f"Attachment Details: {json.dumps(attachment_info, indent=2)}")
                
                # Save to JSON log (only in non-Docker mode)
                json_log_path = Path(self.config.LOG_DIR) / 'attachments.json'
                with open(json_log_path, 'a') as f:
                    f.write(json.dumps(attachment_info) + '\n')
            
            # Process PDF
            if filename.lower().endswith('.pdf') and self.config.ENABLE_SUMMARIZATION:
                self._process_pdf(file_path, attachment_info)
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"Failed to save attachment {filename}: {e}")
            return None
    
    def _process_pdf(self, pdf_path: Path, attachment_info: dict):
        """Extract text and generate document analysis for PDF"""
        try:
            self.logger.info(f"Analyzing PDF document: {pdf_path.name}")
            
            # Extract text
            text = self._extract_pdf_text(pdf_path)
            
            if not text.strip():
                self.logger.warning(f"No text extracted from PDF: {pdf_path.name}")
                return
            
            self.logger.info(f"Extracted {len(text)} characters from PDF for analysis")
            
            # Generate document description/analysis
            summary = self._summarize_text(text)
            
            # Save summary
            summary_path = pdf_path.parent / f"{pdf_path.stem}_summary.txt"
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(f"PDF Document Analysis for: {attachment_info['original_filename']}\n")
                f.write(f"From: {attachment_info['sender']}\n")
                f.write(f"Subject: {attachment_info['subject']}\n")
                f.write(f"Processed: {datetime.now().isoformat()}\n")
                f.write(f"File Size: {attachment_info['file_size']} bytes\n")
                f.write("-" * 50 + "\n\n")
                f.write("DOCUMENT DESCRIPTION:\n")
                f.write(summary)
                f.write("\n\n" + "-" * 50 + "\n")
                f.write("CONTENT PREVIEW (first 1000 characters):\n")
                # Save first 1000 characters of full text as preview
                preview_length = min(1000, len(text))
                f.write(text[:preview_length])
                if len(text) > preview_length:
                    f.write(f"\n\n... (document continues for {len(text)} total characters)")
            
            self.logger.info(f"Generated document analysis: {summary_path.name}")
            
        except Exception as e:
            self.logger.error(f"Failed to process PDF {pdf_path}: {e}")
    
    def _process_email(self, email_id: bytes):
        """Process a single email and download attachments"""
        try:
            # Fetch email
            _, msg_data = self.mail.fetch(email_id, '(RFC822)')
            email_body = msg_data[0][1]
            message = email.message_from_bytes(email_body)
            
            # Extract email details
            sender = self._decode_header_value(message.get('From', ''))
            subject = self._decode_header_value(message.get('Subject', ''))
            date = message.get('Date', '')
            
            # Create timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if self.docker_mode:
                self.logger.info(f"📧 Processing email from {sender}")
                if subject:
                    self.logger.info(f"   Subject: {subject[:50]}{'...' if len(subject) > 50 else ''}")
            else:
                self.logger.info(f"Processing email from {sender}: {subject}")
            
            # Check for attachments
            has_attachments = False
            
            for part in message.walk():
                if part.get_content_disposition() == 'attachment':
                    has_attachments = True
                    filename = part.get_filename()
                    
                    if filename:
                        # Decode filename if needed
                        filename = self._decode_header_value(filename)
                        attachment_data = part.get_payload(decode=True)
                        
                        if attachment_data:
                            self._process_attachment(
                                attachment_data, filename, sender, subject, timestamp
                            )
            
            if not has_attachments:
                if self.docker_mode:
                    self.logger.info("   ✉️  No attachments found")
                else:
                    self.logger.info("No attachments found in email")
                
        except Exception as e:
            self.logger.error(f"Failed to process email {email_id}: {e}")
    
    def _process_new_messages(self):
        """Process any new unseen messages"""
        try:
            # Ensure we're connected and have inbox selected
            if not self.mail:
                self.logger.error("No IMAP connection available")
                return
                
            # Re-select inbox to ensure clean state
            self.mail.select('INBOX')
            
            _, message_ids = self.mail.search(None, 'UNSEEN')
            
            if message_ids[0]:
                unseen_ids = message_ids[0].split()
                self.logger.info(f"Processing {len(unseen_ids)} new messages")
                
                for email_id in unseen_ids:
                    self._process_email(email_id)
                    # Mark as seen after processing
                    self.mail.store(email_id, '+FLAGS', '\\Seen')
            else:
                self.logger.debug("No new unseen messages found")
                
        except Exception as e:
            self.logger.error(f"Failed to process new messages: {e}")
            # Try to reconnect if there's a connection issue
            if "connection" in str(e).lower():
                self.logger.info("Connection issue detected, will reconnect on next iteration")
    
    def _monitor_inbox(self):
        """Monitor inbox using IDLE with proper state management"""
        self.logger.info("Starting email monitoring with IDLE...")
        
        while self.running:
            try:
                # Ensure we have a fresh connection
                if not self.mail:
                    if not self._connect_gmail():
                        time.sleep(30)
                        continue
                
                # Select inbox
                self.mail.select('INBOX')
                
                # Start IDLE monitoring
                self.logger.info("Starting IDLE monitoring...")
                
                # Send IDLE command
                tag = self.mail._new_tag()
                if isinstance(tag, bytes):
                    tag = tag.decode()
                self.mail.send(f'{tag} IDLE\r\n'.encode())
                
                # Wait for IDLE acknowledgment
                while True:
                    line = self.mail.readline()
                    line_str = line.decode('utf-8', errors='ignore')
                    if line.startswith(b'+ idling'):
                        self.logger.info("IDLE started successfully")
                        break
                    elif tag in line_str and 'OK' in line_str:
                        self.logger.info("IDLE acknowledged")
                        break
                    elif 'NO' in line_str or 'BAD' in line_str:
                        raise Exception(f"IDLE command failed: {line_str}")
                
                # Monitor for changes
                idle_start_time = time.time()
                while self.running:
                    try:
                        # Set a timeout for readline
                        line = self.mail.readline()
                        
                        if line:
                            line_str = line.decode('utf-8', errors='ignore')
                            self.logger.debug(f"IDLE response: {line_str.strip()}")
                            
                            # Check for new messages
                            if 'EXISTS' in line_str:
                                self.logger.info("NEW EMAIL DETECTED via IDLE!")
                                
                                # Terminate IDLE properly
                                self.mail.send(b'DONE\r\n')
                                
                                # Wait for IDLE termination confirmation
                                while True:
                                    resp = self.mail.readline()
                                    if tag in resp.decode('utf-8', errors='ignore'):
                                        break
                                
                                # Process new messages
                                self._process_new_messages()
                                
                                # Break to restart IDLE
                                break
                        
                        # Restart IDLE every 29 minutes (Gmail times out at 30 minutes)
                        if time.time() - idle_start_time > 1740:  # 29 minutes
                            self.logger.info("Restarting IDLE (timeout prevention)")
                            self.mail.send(b'DONE\r\n')
                            
                            # Wait for IDLE termination
                            while True:
                                resp = self.mail.readline()
                                if tag in resp.decode('utf-8', errors='ignore'):
                                    break
                            break
                            
                    except Exception as e:
                        self.logger.error(f"Error during IDLE monitoring: {e}")
                        # Try to terminate IDLE gracefully
                        try:
                            self.mail.send(b'DONE\r\n')
                        except:
                            pass
                        break
                        
            except Exception as e:
                self.logger.error(f"IDLE setup failed: {e}")
                self.logger.info("Falling back to polling for this iteration...")
                
                # Close current connection and reconnect
                try:
                    if self.mail:
                        self.mail.logout()
                except:
                    pass
                self.mail = None
                
                # Use polling as fallback for one cycle
                if self._connect_gmail():
                    self._poll_once()
                
                time.sleep(10)  # Wait before retrying IDLE
    
    def _poll_once(self):
        """Check for new messages once (used as IDLE fallback)"""
        try:
            self.mail.select('INBOX')
            _, message_ids = self.mail.search(None, 'UNSEEN')
            
            if message_ids[0]:
                unseen_ids = message_ids[0].split()
                if unseen_ids:
                    self.logger.info(f"Found {len(unseen_ids)} unseen messages (polling)")
                    
                    for email_id in unseen_ids:
                        self._process_email(email_id)
                        self.mail.store(email_id, '+FLAGS', '\\Seen')
                        
        except Exception as e:
            self.logger.error(f"Error during single poll: {e}")
    
    def _poll_inbox(self):
        """Fallback polling method if IDLE doesn't work"""
        self.logger.info("Starting polling mode (checking every 10 seconds)...")
        
        while self.running:
            try:
                # Ensure connection is still active
                if not self.mail:
                    self.logger.warning("IMAP connection lost, attempting to reconnect...")
                    if not self._connect_gmail():
                        time.sleep(30)
                        continue
                
                # Refresh the inbox
                self.mail.select('INBOX')
                
                # Check for unseen messages
                _, message_ids = self.mail.search(None, 'UNSEEN')
                
                if message_ids[0]:
                    unseen_ids = message_ids[0].split()
                    self.logger.info(f"Found {len(unseen_ids)} unseen messages")
                    
                    for email_id in unseen_ids:
                        self._process_email(email_id)
                        # Mark as seen after processing
                        self.mail.store(email_id, '+FLAGS', '\\Seen')
                else:
                    self.logger.debug("No new unseen messages")
                
                # Wait before next check (reduced to 10 seconds for faster detection)
                time.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Error during polling: {e}")
                # If it's a connection error, try to reconnect
                if "connection" in str(e).lower() or "socket" in str(e).lower():
                    self.logger.info("Connection error detected, attempting to reconnect...")
                    self.mail = None
                    if self._connect_gmail():
                        continue
                time.sleep(10)
    
    def start(self):
        """Start monitoring Gmail"""
        if self.docker_mode:
            self.logger.info("📧 Starting Gmail monitoring...")
            self.logger.info(f"📁 Attachments will be saved to: {self.attachments_dir}")
            if self.config.ENABLE_SUMMARIZATION:
                self.logger.info("📄 PDF summarization is enabled")
            else:
                self.logger.info("📄 PDF summarization is disabled")
        else:
            self.logger.info("=" * 50)
            self.logger.info("Gmail Attachment Watcher Starting")
            self.logger.info(f"Attachments Dir: {self.attachments_dir}")
            self.logger.info(f"Summarization: {'Enabled' if self.config.ENABLE_SUMMARIZATION else 'Disabled'}")
            self.logger.info("=" * 50)
        
        # Connect to Gmail
        if not self._connect_gmail():
            self.logger.error("Failed to connect to Gmail. Exiting.")
            return
        
        # Process any existing unseen messages
        try:
            _, message_ids = self.mail.search(None, 'UNSEEN')
            if message_ids[0]:
                unseen_count = len(message_ids[0].split())
                if self.docker_mode:
                    self.logger.info(f"📬 Processing {unseen_count} existing unread emails...")
                else:
                    self.logger.info(f"Processing {unseen_count} existing unseen messages")
                for email_id in message_ids[0].split():
                    self._process_email(email_id)
                    self.mail.store(email_id, '+FLAGS', '\\Seen')
        except Exception as e:
            self.logger.error(f"Failed to process existing messages: {e}")
        
        # Start monitoring
        self._monitor_inbox()

def main():
    """Main entry point"""
    config = Config()
    # Check if running in Docker mode (detect by checking if we're in Docker environment)
    docker_mode = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
    watcher = GmailAttachmentWatcher(config, docker_mode=docker_mode)
    watcher.start()

if __name__ == "__main__":
    main()