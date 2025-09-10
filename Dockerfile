# CPU-only AI Docker build
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for compilation
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Upgrade pip for better dependency resolution
RUN pip install --upgrade pip

# Copy requirements
COPY requirements-docker.txt .

# Install Python dependencies in steps to avoid memory issues
RUN pip install --no-cache-dir python-dotenv imapclient pdfplumber PyPDF2 requests pillow numpy

# Install PyTorch CPU-only (smaller download)
RUN pip install --no-cache-dir torch==2.1.2+cpu -f https://download.pytorch.org/whl/torch_stable.html

# Install transformers and dependencies
RUN pip install --no-cache-dir transformers==4.36.2 tokenizers==0.15.0 tqdm pyyaml filelock huggingface-hub safetensors regex packaging

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY docker-entrypoint.py .

# Create volume mount point for attachments
RUN mkdir -p /app/attachments

# Set environment variables for CPU-only operation
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV FORCE_CPU=true
ENV TORCH_HOME=/tmp/torch
ENV HF_HOME=/tmp/huggingface

# Expose volume for attachments
VOLUME ["/app/attachments"]

# Run the interactive setup script
ENTRYPOINT ["python", "docker-entrypoint.py"]
