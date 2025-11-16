# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy only requirements and install
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y libopenblas-dev build-essential && \
    pip install --upgrade pip && \
    pip install -r requirements.txt && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy only the Python script
COPY insert_news.py news_scraper.py ./
COPY lib/ ./lib/ 

# Default command
CMD ["python", "insert_news.py"]
