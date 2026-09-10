FROM python:3.11-slim

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your Python application
COPY . .

# Copy and set permissions for run script
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh

# Create output directory
RUN mkdir -p /app/output

# Set up cron job to run every 12 hours
RUN echo "0 10,22 * * * /app/run.sh >> /var/log/cron.log 2>&1" | crontab -

# Create log file
RUN touch /var/log/cron.log

# Run cron in foreground and tail the log
CMD cron && tail -f /var/log/cron.log

# Copy and set permissions for entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Execute the run script once at startup
CMD ["/app/entrypoint.sh"]