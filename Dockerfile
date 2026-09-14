FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create logs directory
RUN mkdir -p logs

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python3 -c "import micro_apex; print('OK')" || exit 1

# Run the trading system
CMD ["python3", "app.py"]
