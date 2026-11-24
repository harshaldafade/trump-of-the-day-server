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
    verb = article("Local bakery trumps the competition again")
    assert score_article(verb) < score_article(article("Local bakery beats the competition again"))


def test_trump_followed_by_the_is_the_person_not_the_idiom():
    for title in ("Trump the environmentalist? How his Iran war exposed dirty energy",
                  "TV networks deny Trump the one thing he craves most: attention"):
        assert score_article(article(title)) >= 3.0  # the name bonus, no idiom penalty


def test_reputable_source_adds_score_and_missing_metadata_doesnt_matter():
    base = article("Trump meets Zelenskyy at the White House")
    reputable = article("Trump meets Zelenskyy at the White House", link="https://www.reuters.com/world/x")
    assert score_article(reputable) == score_article(base) + 1.5
    rich = article("Trump meets Zelenskyy at the White House", description="The leaders met.",
                   image_url="https://img/x.jpg")
    assert score_article(rich) == score_article(base)


def test_subdomains_of_reputable_outlets_count():
    assert score_article(article("Trump tariffs explained", link="https://edition.cnn.com/x")) > \
        score_article(article("Trump tariffs explained", link="https://cnn.com.example.net/x"))


def test_google_redirects_score_like_any_other_link():
    google = article("Trump tariffs explained", link="https://news.google.com/rss/articles/abc")
    assert score_article(google) == score_article(article("Trump tariffs explained"))


def test_rank_is_best_first_and_stable():
    a = article("Trump visits Texas border crossing", link="https://a.com/1")
    b = article("Trump visits Texas border crossing", link="https://b.com/2")
    c = article("Weather update for the weekend")
    assert rank([c, a, b]) == [a, b, c]


def test_officials_us_government_and_policy_fronts_count_without_his_name():
    for title in ("The long-term implications of Pete Hegseth's US military purges",
                  "U . S . strikes targets in Iran as hostilities flare",
                  "Scott Bessent awaits Nvidia answers on AI chips"):
        assert score_article(article(title)) > 0, title
    assert score_article(article("Join us for the county fair this weekend")) == 0


def test_google_news_rows_get_the_reputable_bonus_from_the_outlet_name():
    base = article("Oil prices slide on hope for more talks", link="https://news.google.com/rss/articles/x",
                   news_source="Some Blog")
    for source in ("The Washington Post", "Reuters", "washingtonpost.com"):
        named = dict(base, news_source=source)
        assert score_article(named) == score_article(base) + 1.5, source
