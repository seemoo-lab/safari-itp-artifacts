FROM python:3.11-slim

# Prevent .pyc files and force stdout/stderr to be unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Create results folder
RUN mkdir -p /app/results

# Install dependencies
COPY export/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project
COPY storage/ ./storage/
COPY export/main.py .

# Run python main.py when the container starts
CMD ["python", "main.py"]
