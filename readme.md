# Local Development

You can run the Gmail Attachment Watcher locally for development and testing.

### Prerequisites

- Python 3.8 or newer
- Install dependencies:
  ```sh
  pip install -r requirements-docker.txt
  ```
- Create a `.env` file in the project root with your Gmail credentials and configuration. Example:
  ```env
  GMAIL_ADDRESS=your-email@gmail.com
  GMAIL_PASSWORD=your-app-password
  ENABLE_SUMMARIZATION=true
  SUMMARIZATION_MODEL=t5-small
  ATTACHMENTS_DIR=./data/attachments
  LOG_DIR=./data/logs
  ```

### Running Locally

1. Make sure your `.env` file is present in the project root.
2. Run the watcher:
   ```sh
   python run-local.py
   ```
3. Follow the console output for status and logs.
4. Attachments and summaries will be saved in the `data/attachments` folder.
# 🐳 Docker Hub Repository: mail-wacher

**Repository URL:** [https://hub.docker.com/r/jayanshn/mail-wacher](https://hub.docker.com/r/jayanshn/mail-wacher)

This repository hosts the official Docker image for Gmail Attachment Watcher. Pull and run the image to monitor your Gmail inbox for attachments and generate AI-powered PDF summaries automatically. No manual setup required—just run the container and follow the interactive prompts.

---
### Using Docker Compose

You can use Docker Compose for easier setup and management. Create a file named `docker-compose.yml` in your project folder with the following content:

```yaml
version: '3.8'
services:
  gmail-watcher:
    image: jayanshn/mail-wacher:latest
    container_name: gmail-attachment-watcher
    stdin_open: true
    tty: true
    volumes:
      - ./attachments:/app/attachments
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
```

**Steps:**
1. Create an `attachments` folder:
   ```sh
   mkdir attachments
   ```
2. Create the above `docker-compose.yml` file in your project directory.
3. Start the service:
   ```sh
   docker-compose up
   ```
4. Follow the interactive prompts in the container to complete setup.

This method is recommended for repeatable deployments and easier configuration management.

# 📧 Gmail Attachment Watcher - Docker Edition

Monitor your Gmail for attachments and automatically generate AI summaries for PDF documents!

## 🚀 Quick Start

### Prerequisites
- Docker installed
- Gmail account with App Password enabled ([How to set up](https://myaccount.google.com/security))

### Run with Docker

1. **Create an attachments folder:**
   ```sh
   mkdir attachments
   ```
2. **Start the container:**
   ```sh
   docker run -it --rm -v %cd%/attachments:/app/attachments jayanshn/mail-wacher:latest
   ```
   - For Windows, use `%cd%/attachments` or `%cd%\attachments` as appropriate.
3. **Or use Docker Compose:**
   ```sh
   docker-compose up
   ```

### First Run Setup

When you start the container, you'll be prompted for:
- Gmail address
- App Password (not your regular password)
- Whether to enable PDF summarization
- Model selection (fast or high-quality)

### How It Works

- **Attachments** are saved to your `attachments` folder
- **PDF summaries** are saved as `_summary.txt` next to each PDF
- Logs are shown in the console

### Features

- Real-time Gmail monitoring
- Automatic attachment downloading
- AI-powered PDF summarization (CPU-only)
- Intelligent document analysis

### Example Output

```
📧 GMAIL ATTACHMENT WATCHER
====================================
📧 Starting Gmail monitoring...
📁 Attachments will be saved to: /app/attachments
📄 PDF summarization is enabled
✅ Gmail connection successful!
📬 Processing 2 existing unread emails...
📧 Processing email from john@example.com
   Subject: Important Document
📎 Saved: report.pdf (125KB) from john@example.com
📄 Analyzing PDF document: report.pdf
✅ Generated document analysis: report_summary.txt
```

### Troubleshooting

- **Connection failed?**
  - Use App Password, not your regular password
  - Ensure 2-Factor Authentication is enabled
  - Double-check your Gmail address
- **No emails detected?**
  - Send yourself a test email with an attachment
  - Check Gmail filters and spam
- **Summarization not working?**
  - Ensure you have enough RAM (4GB+ recommended)
  - Try the "fast" model option

### Advanced Configuration

You can customize behavior by editing environment variables in `docker-compose.yml`:

```yaml
environment:
  - FORCE_CPU=true              # Force CPU-only processing
  - MAX_INPUT_LENGTH=1024       # Max text length for summarization
  - SUMMARY_MAX_LENGTH=200      # Max summary length
  - SUMMARY_MIN_LENGTH=50       # Min summary length
```

### Security Notes

- App Passwords are more secure than regular passwords
- No credentials are stored permanently
- All processing happens locally
- No data is sent to external services (except for downloading AI models)

---

**Happy monitoring!** 📧✨
