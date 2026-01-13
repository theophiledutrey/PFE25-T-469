FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y openssh-client sshpass zsh && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install dependencies (including ansible which is required but seemingly missing from requirements)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Install the application in editable mode to preserve directory structure assumptions
RUN pip install -e .

# Expose the port NiceGUI runs on
EXPOSE 54540

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV REEF_HOST=0.0.0.0
ENV REEF_PORT=54540

# Run the application
CMD ["reef"]
