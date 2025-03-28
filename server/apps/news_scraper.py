import requests
from bs4 import BeautifulSoup
import datetime

GOOGLE_NEWS_URL = "https://www.google.com/search?q=Donald+Trump&tbm=nws&tbs=cdr:1,cd_min:{},cd_max={}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def fetch_image_from_meta(url):
    """Fetches the main image URL from a news article using Open Graph and Twitter meta tags."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        # Check Open Graph Image
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]

        # Check Twitter Image
        twitter_image = soup.find("meta", property="twitter:image")
        if twitter_image and twitter_image.get("content"):
            return twitter_image["content"]

    except requests.RequestException:
        return ""

    return ""

def fetch_news_by_date(target_date):
    """Scrapes Google News for Trump-related news on a specific date."""
    formatted_date = target_date.strftime("%m/%d/%Y")
    url = GOOGLE_NEWS_URL.format(formatted_date, formatted_date)

    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"❌ Failed to fetch news for {formatted_date}. Status Code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select("div.SoaBEf")  # Google News article container

    if not articles:
        print(f"⚠️ No articles found for {formatted_date}.")
        return []

    news_list = []
    for article in articles:
        title_tag = article.select_one("div.n0jPhd")
        link_tag = article.select_one("a.WlydOe")
        desc_tag = article.select_one("div.GI74Re")
        source_tag = article.select_one("div.MgUUmf span")

        # Extract title
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Extract link
        link = link_tag["href"] if link_tag else ""

        # Extract description/snippet
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        # Extract news source
        news_source = source_tag.get_text(strip=True) if source_tag else ""

        # ✅ Fetch image from the news article's metadata
        image_url = fetch_image_from_meta(link)

        news_list.append({
            "title": title,
            "link": link,
            "description": description,
            "news_source": news_source,
            "image_url": image_url,
            "date": target_date.strftime("%Y-%m-%d")
        })

    return news_list

if __name__ == "__main__":
    test_date = datetime.date.today()
    articles = fetch_news_by_date(test_date)
    for article in articles:
        print(article)  # ✅ Now check if image_url is properly extracted!
