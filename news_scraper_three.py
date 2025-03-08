import os
import argparse
import requests
import hashlib
import feedparser
import datetime
import time
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Connect to Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Table name in Supabase
TABLE_NAME = "news_articles"

# ✅ List of Reliable RSS Feeds (Only trusted sources)
RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",
    "https://feeds.a.dj.com/rss/RSSPolitics.xml",
    "https://www.theguardian.com/us-news/rss",
    "https://apnews.com/rss",
    "https://feeds.foxnews.com/foxnews/politics",
    "https://www.npr.org/rss/rss.php?id=1014",
    "https://www.reutersagency.com/feed/?taxonomy=best-sectors&post_type=best",
    "https://www.cbsnews.com/latest/rss/politics",
]

# ✅ Keywords to Filter for Trump-related News
TRUMP_KEYWORDS = [
    "Trump", "Donald Trump", "ex-president", "former president","president Trump",
    "Trump campaign", "Trump rally", "MAGA", "Trump administration"
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_rss_articles(start_date, end_date):
    """Fetches Trump-related news from RSS feeds within a date range."""
    news_articles = []
    for feed_url in RSS_FEEDS:
        try:
            print(f"🔍 Fetching RSS from {feed_url}...")
            feed = feedparser.parse(feed_url)
            if "entries" not in feed or not feed.entries:
                print(f"⚠️ No entries found in {feed_url}. Skipping.")
                continue

            for entry in feed.entries:
                title = entry.get("title", "")
                if not any(keyword.lower() in title.lower() for keyword in TRUMP_KEYWORDS):
                    continue  # Skip articles not related to Trump

                article_date = parse_published_date(entry.get("published", ""))
                if not article_date or not (start_date <= article_date.date() <= end_date):
                    continue  # Skip articles outside the date range

                news_articles.append({
                    "title": title,
                    "url": entry.get("link", ""),
                    "description": entry.get("summary", ""),
                    "image_url": extract_image_from_meta(entry.get("link", "")),
                    "news_source": feed.feed.get("title", "Unknown Source"),
                    "published_at": article_date.strftime("%Y-%m-%d %H:%M:%S"),
                })
        except Exception as e:
            print(f"❌ Failed to fetch RSS from {feed_url}: {e}")
    return news_articles


def extract_image_from_meta(url):
    """Scrapes OpenGraph/Twitter meta tags to find the main image of the article."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]

        twitter_image = soup.find("meta", property="twitter:image")
        if twitter_image and twitter_image.get("content"):
            return twitter_image["content"]
    except requests.RequestException:
        return ""

    return ""


def parse_published_date(date_str):
    """Parses various RSS date formats into PostgreSQL timestamp format."""
    if not date_str:
        return None

    try:
        parsed_date = date_parser.parse(date_str)
        return parsed_date
    except Exception as e:
        print(f"❌ Error parsing date '{date_str}': {e}")
        return None


def scrape_missing_fields(article):
    """Scrapes missing fields like full_text from the article page."""
    if not article.get("url"):
        return article

    try:
        response = requests.get(article["url"], headers=HEADERS, timeout=5)
        if response.status_code != 200:
            return article

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract full article text
        paragraphs = soup.find_all("p")
        full_text = "\n".join(p.get_text() for p in paragraphs)
        article["full_text"] = full_text

        # Extract an image if missing
        if not article["image_url"]:
            article["image_url"] = extract_image_from_meta(article["url"])
    except requests.RequestException:
        return article

    return article


def save_news_to_supabase(news_articles):
    """Inserts news articles into Supabase, avoiding duplicates."""
    for article in news_articles:
        article = scrape_missing_fields(article)

        # Generate hash of URL to avoid duplicates
        url_hash = hashlib.sha256(article["url"].encode()).hexdigest()

        data = {
            "title": article["title"],
            "url": article["url"],
            "url_hash": url_hash,
            "description": article.get("description", ""),
            "full_text": article.get("full_text", ""),
            "image_url": article.get("image_url", ""),
            "source": article["news_source"],
            "published_at": article["published_at"],
            "created_at": datetime.datetime.utcnow().isoformat(),
        }

        if not data["published_at"]:
            print(f"⚠️ Skipping {article['title']} due to missing date")
            continue

        # Insert into Supabase (avoiding duplicates)
        try:
            existing = supabase.table(TABLE_NAME).select("id").eq("url_hash", url_hash).execute()
            if existing.data:  # ✅ Fixed: Checking correctly
                print(f"⚠️ Article already exists: {article['title']}")
                continue

            response = supabase.table(TABLE_NAME).insert(data).execute()
            if response.data:  # ✅ Fixed: Correct way to check response
                print(f"✅ Inserted: {article['title']}")
            else:
                print(f"❌ Insert failed: {response}")
        except Exception as e:
            print(f"❌ Exception while inserting data: {e}")


def run_scraper(start_date, end_date):
    """Main function to fetch, filter, and insert Trump-related news."""
    print(f"📡 Fetching Trump-related news from {start_date} to {end_date}...")
    news_articles = fetch_rss_articles(start_date, end_date)
    
    if not news_articles:
        print("⚠️ No Trump-related articles found.")
        return

    print(f"📌 {len(news_articles)} articles found. Saving to database...")
    save_news_to_supabase(news_articles)
    print("🎉 Done fetching and saving news!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch Trump-related news from RSS feeds.")
    parser.add_argument("--start_date", type=str, required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end_date", type=str, required=True, help="End date in YYYY-MM-DD format")
    
    args = parser.parse_args()

    try:
        start_date = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(args.end_date, "%Y-%m-%d").date()
    except ValueError:
        print("❌ Invalid date format. Use YYYY-MM-DD.")
        exit(1)

    run_scraper(start_date, end_date)
