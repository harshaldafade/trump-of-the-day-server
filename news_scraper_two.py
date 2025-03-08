import feedparser
import requests
import hashlib
import asyncpg
import os
import datetime
import time
from newspaper import Article
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm  # For progress bar

# Load environment variables
load_dotenv()

# Supabase Database URL and Key
SUPABASE_DB_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")

# Trusted RSS Feeds (Trump-related)
RSS_FEEDS = [
    "https://www.reutersagency.com/feed/?best-topics=politics&post_type=best",
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://www.cbsnews.com/latest/rss/politics",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.cnbc.com/id/10000113/device/rss/rss.html",
    "https://www.politico.com/rss/politics.xml",
    "https://www.foxnews.com/about/rss",
    "https://www.nbcnews.com/rss/politics",
    "https://apnews.com/hub/politics/rss",
    "https://www.bbc.co.uk/news/10628494",
]

# Keywords to filter Trump-related news
TRUMP_KEYWORDS = ["Trump", "Donald Trump", "ex-president", "former president", "MAGA"]

async def connect_db():
    """ Connect to Supabase database """
    return await asyncpg.connect(SUPABASE_DB_URL)

def hash_url(url):
    """ Generate a SHA256 hash of the article URL for deduplication """
    return hashlib.sha256(url.encode()).hexdigest()

def scrape_article(url):
    """ Scrape article content if RSS feed lacks required data """
    try:
        article = Article(url)
        article.download()
        article.parse()

        return {
            "title": article.title,
            "description": article.meta_description or article.text[:300],  # Extract summary if missing
            "image_url": article.top_image if article.top_image else None,
            "full_text": article.text  # Full article content
        }
    except Exception as e:
        print(f"❌ Failed to scrape {url}: {e}")
        return None

async def fetch_and_store_news():
    """ Fetch news from RSS feeds, scrape missing fields, and store in Supabase """
    conn = await connect_db()
    total_articles = 0

    for feed_url in RSS_FEEDS:
        print(f"📡 Fetching: {feed_url}")
        feed = feedparser.parse(feed_url)

        for entry in tqdm(feed.entries, desc="Processing Articles", unit="article"):
            title = entry.title
            url = entry.link
            description = entry.summary if "summary" in entry else None
            image_url = entry.media_content[0]["url"] if "media_content" in entry and entry.media_content else None
            source = feed.feed.title if "title" in feed.feed else "Unknown"
            published_at = entry.published if "published" in entry else datetime.datetime.utcnow().isoformat()

            # Convert published_at to timestamp
            try:
                published_at = datetime.datetime.strptime(published_at, "%a, %d %b %Y %H:%M:%S %Z")
            except ValueError:
                published_at = datetime.datetime.utcnow()

            # Skip articles that are not related to Trump
            if not any(keyword.lower() in title.lower() for keyword in TRUMP_KEYWORDS):
                continue

            url_hash = hash_url(url)

            # Check if article already exists in DB
            existing_article = await conn.fetchrow(
                "SELECT id, description, image_url, full_text FROM news_articles WHERE url_hash=$1", url_hash
            )
            if existing_article:
                # If article exists but is missing fields, update it
                if not existing_article["description"] or not existing_article["image_url"] or not existing_article["full_text"]:
                    print(f"🔄 Updating missing fields for: {title}")
                    scraped_data = scrape_article(url)
                    if scraped_data:
                        description = description or scraped_data.get("description")
                        image_url = image_url or scraped_data.get("image_url")
                        full_text = scraped_data.get("full_text") if not existing_article["full_text"] else existing_article["full_text"]

                        await conn.execute(
                            """
                            UPDATE news_articles 
                            SET description=$1, image_url=$2, full_text=$3
                            WHERE url_hash=$4
                            """,
                            description, image_url, full_text, url_hash
                        )
                else:
                    print(f"⚠️ Skipping duplicate: {title}")
                continue  # Skip inserting duplicate

            # If missing fields, scrape the full article
            full_text = None
            if not description or not image_url:
                scraped_data = scrape_article(url)
                if scraped_data:
                    description = description or scraped_data.get("description")
                    image_url = image_url or scraped_data.get("image_url")
                    full_text = scraped_data.get("full_text")

            # Insert into Supabase
            try:
                await conn.execute(
                    """
                    INSERT INTO news_articles (title, url, url_hash, description, full_text, summary_gen, summary_gen_bool, image_url, source, published_at, created_at)
                    VALUES ($1, $2, $3, $4, $5, NULL, FALSE, $6, $7, $8, now())
                    """,
                    title, url, url_hash, description, full_text, image_url, source, published_at
                )
                print(f"✅ Inserted: {title}")
                total_articles += 1
            except Exception as e:
                print(f"❌ Error inserting {title}: {e}")

    await conn.close()
    print(f"🚀 Finished inserting {total_articles} articles!")

# Run the fetcher
import asyncio
asyncio.run(fetch_and_store_news())
