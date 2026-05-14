from app.wikipedia_fetcher import WikipediaFetcher, Article


def test_search_returns_article_with_required_fields():
    fetcher = WikipediaFetcher()
    article = fetcher.search("black holes")
    assert isinstance(article, dict)
    assert article["title"]
    assert len(article["summary"]) > 100
    assert article["url"].startswith("https://en.wikipedia.org")
    assert isinstance(article["see_also"], list)


def test_search_unknown_query_returns_empty_article():
    fetcher = WikipediaFetcher()
    article = fetcher.search("xyzzy_nonexistent_topic_12345_zqwerty")
    assert article["title"] == ""
    assert article["summary"] == ""
    assert article["url"] == ""
    assert article["see_also"] == []
