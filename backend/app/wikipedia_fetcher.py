import requests
import wikipediaapi
from typing import TypedDict


class Article(TypedDict):
    title: str
    summary: str
    url: str
    see_also: list[str]
    image_url: str


_EMPTY_ARTICLE: Article = {"title": "", "summary": "", "url": "", "see_also": [], "image_url": ""}

_USER_AGENT = "RabbitPedia/1.0 (hamid.sarfraz1995@gmail.com)"


class WikipediaFetcher:
    def __init__(self):
        self._wiki = wikipediaapi.Wikipedia(
            language="en",
            user_agent=_USER_AGENT,
        )

    def _fetch_image(self, title: str) -> str:
        try:
            resp = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": title,
                    "prop": "pageimages",
                    "pithumbsize": 300,
                    "format": "json",
                },
                headers={"User-Agent": _USER_AGENT},
                timeout=4,
            )
            pages = resp.json().get("query", {}).get("pages", {})
            for page in pages.values():
                src = page.get("thumbnail", {}).get("source", "")
                if src:
                    return src
        except Exception:
            pass
        return ""

    def search(self, query: str) -> Article:
        page = self._wiki.page(query)
        if not page.exists():
            resp = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "opensearch",
                    "search": query,
                    "limit": 1,
                    "format": "json",
                },
                headers={"User-Agent": _USER_AGENT},
                timeout=10,
            )
            results = resp.json()
            if not results[1]:
                return _EMPTY_ARTICLE
            page = self._wiki.page(results[1][0])
            if not page.exists():
                return _EMPTY_ARTICLE

        image_url = self._fetch_image(page.title)

        return Article(
            title=page.title,
            summary=page.summary,
            url=page.fullurl,
            see_also=list(page.links.keys())[:10],
            image_url=image_url,
        )

    def get_full_text(self, title: str) -> str:
        try:
            page = self._wiki.page(title)
            if page.exists():
                return page.text
        except Exception:
            pass
        return ""

    def extract_controversy_paragraphs(self, full_text: str, max_paras: int = 12) -> list[str]:
        _SIGNALS = [
            "criticized", "controversy", "controversial", "disputed", "dispute",
            "failed", "failure", "however", "critics", "critic", "opposed",
            "opposition", "despite", "argued", "argument", "backlash",
            "condemned", "rejected", "questioned", "debated", "problematic",
            "concern", "protest", "scandal", "alleged", "accusation",
        ]
        results = []
        for para in full_text.split("\n"):
            para = para.strip()
            if len(para) < 60:
                continue
            lower = para.lower()
            if any(sig in lower for sig in _SIGNALS):
                results.append(para)
                if len(results) >= max_paras:
                    break
        return results

    def get_links(self, title: str, limit: int = 40) -> list[str]:
        try:
            resp = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "titles": title,
                    "prop": "links",
                    "pllimit": limit,
                    "plnamespace": 0,
                    "format": "json",
                },
                headers={"User-Agent": _USER_AGENT},
                timeout=10,
            )
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                links = page.get("links", [])
                return [link["title"] for link in links]
        except Exception:
            pass
        return []

    def deep_search(self, query: str, max_articles: int = 3) -> list[Article]:
        primary = self.search(query)
        if not primary["title"]:
            return [primary]

        articles: list[Article] = [primary]
        seen_titles = {primary["title"].lower()}

        scope_suffixes = ["history", "impact"]
        for suffix in scope_suffixes:
            if len(articles) >= max_articles:
                break
            sub = self.search(f"{query} {suffix}")
            if not sub["title"] or not sub["summary"]:
                continue
            if sub["title"].lower() in seen_titles:
                continue
            seen_titles.add(sub["title"].lower())
            articles.append(sub)

        if len(articles) < max_articles:
            for related_title in primary["see_also"]:
                if len(articles) >= max_articles:
                    break
                if related_title.lower() in seen_titles:
                    continue
                try:
                    page = self._wiki.page(related_title)
                    if not page.exists() or not page.summary:
                        continue
                    seen_titles.add(page.title.lower())
                    articles.append(Article(
                        title=page.title,
                        summary=page.summary,
                        url=page.fullurl,
                        see_also=[],
                        image_url="",
                    ))
                except Exception:
                    continue

        return articles
