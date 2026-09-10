ARG BASE_PLATFORM=linux/amd64
FROM --platform=${BASE_PLATFORM} python:3.11-slim

# Prevent .pyc files and force stdout/stderr to be unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create results folder
RUN mkdir -p /app/results

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first so Docker can cache this layer
# and skip reinstalling when only your source code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project
COPY . .

# Make the run.sh script executable and set it as the entrypoint
RUN chmod +x run.sh
CMD ["./run.sh"]