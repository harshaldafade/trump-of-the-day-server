from lib import completeness


def article(link="https://example.com/a", description="", image_url=""):
    return {"title": "Trump signs order", "link": link, "description": description,
            "image_url": image_url}


def test_missing_fields_treats_placeholders_as_missing():
    assert completeness.missing_fields(article(description="Text", image_url="https://i/x.jpg")) == []
    assert completeness.missing_fields(article(image_url="No Image Available")) == ["description", "image_url"]
    assert completeness.missing_fields(article(description="  ", image_url="https://i/x.jpg")) == ["description"]


def test_complete_refetches_only_incomplete_real_links(monkeypatch):
    fetched = []

    def fake_meta(url, session):
        fetched.append(url)
        return {"description": "From the page", "image": "https://i/ok.jpg"}

    monkeypatch.setattr(completeness, "fetch_meta", fake_meta)
    monkeypatch.setattr(completeness, "is_image_reachable", lambda image, referer, session: True)
    whole = article(link="https://a.com/1", description="Already here", image_url="https://i/a.jpg")
    no_image = article(link="https://b.com/2", description="Keep me")
    google = article(link="https://news.google.com/rss/articles/abc")

    summary = completeness.complete([whole, no_image, google], session=object())

    assert fetched == ["https://b.com/2"]
    assert no_image == article(link="https://b.com/2", description="Keep me", image_url="https://i/ok.jpg")
    assert whole["image_url"] == "https://i/a.jpg"
    assert summary == {"checked": 3, "incomplete": 2, "refetched": 1,
                       "filled": {"description": 0, "image_url": 1},
                       "still_incomplete": 1, "unfetchable": 1}


def test_complete_drops_images_that_dont_load(monkeypatch):
    monkeypatch.setattr(completeness, "fetch_meta",
                        lambda url, session: {"description": "", "image": "https://i/dead.jpg"})
    monkeypatch.setattr(completeness, "is_image_reachable", lambda image, referer, session: False)
    a = article()

    summary = completeness.complete([a], session=object())

    assert a["image_url"] == "" and a["description"] == ""
    assert summary["still_incomplete"] == 1
