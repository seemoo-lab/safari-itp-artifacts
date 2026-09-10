FROM mcr.microsoft.com/playwright/python:v1.62.0-jammy

# Prevent .pyc files and force stdout/stderr to be unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project
COPY . .

# Make the run.sh script executable and set it as the entrypoint
RUN chmod +x run.sh
CMD ["./run.sh"]