# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy only requirements and install. Everything left in requirements.txt ships
# wheels, so no compiler or BLAS packages are needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the pipeline code
COPY insert_news.py news_scraper.py ./
COPY lib/ ./lib/

RUN useradd --create-home pipeline
USER pipeline

# Default command: re-scrape yesterday (to pick up stories published after the
# previous run) and scrape today. Duplicate links are skipped on insert.
CMD ["python", "insert_news.py", "yesterday", "today"]
