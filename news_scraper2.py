# ✅ news_scraper.py
import requests
from bs4 import BeautifulSoup
import hashlib
import datetime

GOOGLE_NEWS_URL = "https://www.google.com/search?q=Donald+Trump&tbm=nws&tbs=cdr:1,cd_min:{},cd_max={}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def fetch_image_from_meta(url):
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

def fetch_full_text(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code != 200:
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        paragraphs = soup.find_all("p")
        return "\n".join(p.get_text() for p in paragraphs)
    except requests.RequestException:
        return ""

def generate_url_hash(url):
    return hashlib.sha256(url.encode()).hexdigest()

def fetch_news_by_date(target_date):
    formatted_date = target_date.strftime("%m/%d/%Y")
    url = GOOGLE_NEWS_URL.format(formatted_date, formatted_date)
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"❌ Failed to fetch news for {formatted_date}. Status Code: {response.status_code}")
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select("div.SoaBEf")[:20]  # Top 20 only
    if not articles:
        print(f"⚠️ No articles found for {formatted_date}.")
        return []
    news_list = []
    for article in articles:
        title_tag = article.select_one("div.n0jPhd")
        link_tag = article.select_one("a.WlydOe")
        desc_tag = article.select_one("div.GI74Re")
        source_tag = article.select_one("div.MgUUmf span")
        title = title_tag.get_text(strip=True) if title_tag else ""
        link = link_tag["href"] if link_tag else ""
        description = desc_tag.get_text(strip=True) if desc_tag else ""
        source = source_tag.get_text(strip=True) if source_tag else ""
        image_url = fetch_image_from_meta(link)
        full_text = fetch_full_text(link)
        url_hash = generate_url_hash(link)
        news_list.append({
            "title": title,
            "url": link,
            "url_hash": url_hash,
            "description": description,
            "image_url": image_url,
            "source": source,
            "published_at": target_date.strftime("%Y-%m-%d 12:00:00"),
            "created_at": datetime.datetime.utcnow().isoformat(),
            "full_text": full_text
        })
    return news_list
