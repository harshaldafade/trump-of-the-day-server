import requests
from bs4 import BeautifulSoup
import datetime

# Google News search URL for Trump-related articles
GOOGLE_NEWS_URL = "https://www.google.com/search?q=Donald+Trump&tbm=nws"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def fetch_news():
    """Scrapes the latest news about Trump from Google News."""
    response = requests.get(GOOGLE_NEWS_URL, headers=HEADERS)

    if response.status_code != 200:
        print(f"Failed to fetch news. Status Code: {response.status_code}")
        return []

    print("Successfully fetched news page. Parsing now...")

    soup = BeautifulSoup(response.text, "html.parser")

    # Find all news articles
    articles = soup.select("div.SoaBEf")  # Updated selector for news containers

    if not articles:
        print("No articles found. Google may have changed its structure.")
        return []

    news_list = []
    today = datetime.date.today().isoformat()

    for article in articles:
        title_tag = article.select_one("div.MBeuO")
        link_tag = article.select_one("a.WlydOe")

        if title_tag and link_tag:
            title = title_tag.get_text(strip=True)
            link = link_tag["href"]

            news_list.append({
                "title": title,
                "link": link,
                "date": today
            })

    return news_list

if __name__ == "__main__":
    news = fetch_news()
    print(news)
