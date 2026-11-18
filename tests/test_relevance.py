from lib.relevance import rank, score_article


def article(title, link="https://example.com/a", description="", image_url="", news_source="example.com"):
    return {"title": title, "link": link, "description": description,
            "image_url": image_url, "news_source": news_source}


def test_named_headline_beats_passing_mention():
    named = article("Trump signs executive order on federal hiring freeze")
    mention = article("Markets slide on federal hiring freeze", description="President Trump's order ...")
    assert score_article(named) > score_article(mention) > score_article(article("Markets slide on hiring news"))


def test_idioms_are_penalized():
    idiom = article("Defense plays its trump card in overtime win")
    assert score_article(idiom) < score_article(article("Defense wins in overtime thriller"))


def test_reputable_source_and_metadata_add_score():
    base = article("Trump meets Zelenskyy at the White House")
    rich = article("Trump meets Zelenskyy at the White House", link="https://www.reuters.com/world/x",
                   description="The leaders met...", image_url="https://img/x.jpg")
    assert score_article(rich) == score_article(base) + 2.5


def test_subdomains_of_reputable_outlets_count():
    assert score_article(article("Trump tariffs explained", link="https://edition.cnn.com/x")) > \
        score_article(article("Trump tariffs explained", link="https://cnn.com.example.net/x"))


def test_google_redirects_rank_below_real_links():
    google = article("Trump tariffs explained", link="https://news.google.com/rss/articles/abc")
    assert score_article(google) < score_article(article("Trump tariffs explained"))


def test_rank_is_best_first_and_stable():
    a = article("Trump visits Texas border crossing", link="https://a.com/1")
    b = article("Trump visits Texas border crossing", link="https://b.com/2")
    c = article("Weather update for the weekend")
    assert rank([c, a, b]) == [a, b, c]
