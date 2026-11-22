# Use the official Playwright Python image (includes Chromium, Python, and OS dependencies)
FROM mcr.microsoft.com/playwright/python:v1.61.0-jammy

LABEL org.opencontainers.image.title="EcoFlow Keep-Alive" \
      org.opencontainers.image.description="Headless Chromium keep-alive container that keeps EcoFlow cloud MQTT telemetry flowing for Home Assistant." \
      org.opencontainers.image.url="https://nielshh.github.io/ecoflow-keepalive/" \
      org.opencontainers.image.source="https://github.com/nielshh/ecoflow-keepalive" \
      org.opencontainers.image.licenses="MIT"

# Set working directory
WORKDIR /app

# Copy the script
COPY ecoflow_keepalive.py .

# Run the script directly in headless mode with unbuffered output
CMD ["python3", "-u", "ecoflow_keepalive.py"]
