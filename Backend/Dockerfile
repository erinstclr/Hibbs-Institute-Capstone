# Use official Python runtime
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Install system deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app into the container
# (Make sure this includes app.py, templates/, static/ if any, etc.)
COPY . .

# Disable auto browser open inside the container
ENV DISABLE_AUTO_BROWSER=1
ENV PYTHONUNBUFFERED=1

# Port Flask listens on
EXPOSE 5000

# Start the Flask app
CMD ["python", "app.py"]
