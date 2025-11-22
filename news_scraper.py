import requests
from bs4 import BeautifulSoup
import datetime
import json
import re
GOOGLE_NEWS_SEARCH_URL = (
    "https://www.google.com/search?q=Donald+Trump&tbm=nws&tbs=cdr:1,cd_min:{},cd_max:{}"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.6778.204 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}
def extract_css_background(div):
    """Extracts real thumbnail from Google's inline CSS background-image."""
    if not div:
        return ""
    style = div.get("style", "")

    # background-image:url("...")
    m1 = re.search(r'background-image:\s*url\([\'"]?(.*?)[\'"]?\)', style)
    if m1:
        return m1.group(1)

    # background:url("...")
    m2 = re.search(r'background:\s*url\([\'"]?(.*?)[\'"]?\)', style)
    if m2:
        return m2.group(1)

    return ""

def fetch_image_from_meta(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=6)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")

        # OG & Twitter image tags
        for tag in ["og:image", "twitter:image"]:
            meta = soup.find("meta", property=tag)
            if meta and meta.get("content"):
                return meta["content"]

        # JSON-LD fallback
        ld_json_blocks = soup.find_all("script", type="application/ld+json")
        for block in ld_json_blocks:
            try:
                data = json.loads(block.text.strip())

                # JSON-LD single dict
                if isinstance(data, dict):
                    if "image" in data:
                        img = data["image"]
                        if isinstance(img, str):
                            return img
                        if isinstance(img, dict):
                            return img.get("url", "")

                # JSON-LD list
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "image" in item:
                            img = item["image"]
                            if isinstance(img, str):
                                return img
                            if isinstance(img, dict):
                                return img.get("url", "")

            except:
                continue

    except:
        return ""

    return ""

def fetch_news_by_date(target_date):
    formatted_date = target_date.strftime("%m/%d/%Y")
    url = GOOGLE_NEWS_SEARCH_URL.format(formatted_date, formatted_date)
    print("🔍 Search URL:", url)

    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")
    # Google blocks
    article_blocks = soup.select("div.SoaBEf")
    if not article_blocks:
        article_blocks = soup.select("g-card")

    news_list = []

    for block in article_blocks:
        title_tag = block.select_one(".n0jPhd")
        title = title_tag.get_text(strip=True) if title_tag else ""

        desc_tag = block.select_one(".UqSP2b")
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        source_tag = block.select_one(".MgUUmf span")
        news_source = source_tag.get_text(strip=True) if source_tag else ""
        a_tag = block.find("a", href=True)
        link = a_tag["href"] if a_tag else ""
        thumb = ""

        # 1. CSS background-image (new Google layout)
        thumb_div = block.select_one(".T16mof") or block.select_one(".uhHOwf")
        thumb = extract_css_background(thumb_div)

        # 2. <img> tag fallback
        img_tag = block.select_one(".uhHOwf img")
        if not thumb and img_tag:

            # A: data-src (common)
            if img_tag.get("data-src"):
                thumb = img_tag["data-src"]

            # B: normal src that is not transparent GIF
            elif img_tag.get("src") and not img_tag["src"].startswith("data:image/gif"):
                thumb = img_tag["src"]

            # C: REAL BASE64 JPEG thumbnail
            #     - real images start with /9j/ (JPEG header)
            #     - placeholders never start with /9j/
            elif img_tag.get("src", "").startswith("data:image/jpeg;base64,/9j/"):
                thumb = img_tag["src"]

        # 3. LAST RESORT → fetch OG/Twitter/JSON-LD from article
        image_url = thumb or (fetch_image_from_meta(link) if link else "")

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
