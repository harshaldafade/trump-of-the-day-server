import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

# Set up undetected Chrome driver
options = webdriver.ChromeOptions()
options.add_argument("--headless")  # Runs without opening the browser
options.add_argument("--disable-blink-features=AutomationControlled")  # Avoid bot detection
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = uc.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Target Reuters Trump News Page
URL = "https://www.reuters.com/world/us/donald-trump/"
driver.get(URL)
time.sleep(5)  # Wait for page to load

# Scroll down to load more articles
for _ in range(5):
    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
    time.sleep(2)

# Scrape article headlines & links
articles = driver.find_elements(By.CSS_SELECTOR, "article h3 a")

news_data = []

for article in articles:
    title = article.text.strip()
    link = article.get_attribute("href")

    # Filter only Trump-related articles
    if "trump" in title.lower():
        print(f"📰 {title} - {link}")
        news_data.append({"title": title, "link": link})

driver.quit()

# Save data locally as JSON
with open("trump_news.json", "w", encoding="utf-8") as f:
    json.dump(news_data, f, indent=4)

print(f"\n✅ {len(news_data)} Trump-related articles saved to trump_news.json")
