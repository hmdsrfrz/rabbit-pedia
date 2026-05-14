import asyncio
from typing import List, Set
import httpx
from pydantic import BaseModel
from app.wikipedia_fetcher import Article

_WIKI_API = "https://en.wikipedia.org/w/api.php"
_WIKI_REST = "https://en.wikipedia.org/api/rest_v1"
_HEADERS = {"User-Agent": "RabbitPedia/1.0 (hamid.sarfraz1995@gmail.com)"}
_TIMEOUT = 8


class GraphNode(BaseModel):
    id: str
    summary: str


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str
    explanation: str


class GraphData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    origin: str


async def _fetch_summary(client: httpx.AsyncClient, title: str) -> str:
    try:
        slug = title.replace(" ", "_")
        resp = await client.get(
            f"{_WIKI_REST}/page/summary/{slug}",
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            extract = resp.json().get("extract", "")
            sentence = extract.split(".")[0]
            return (sentence + ".") if sentence else title
    except Exception:
        pass
    return title


async def _fetch_links(client: httpx.AsyncClient, title: str, limit: int = 50) -> Set[str]:
    try:
        resp = await client.get(
            _WIKI_API,
            params={
                "action": "query",
                "titles": title,
                "prop": "links",
                "pllimit": limit,
                "plnamespace": 0,
                "format": "json",
                "redirects": 1,
            },
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return set()
        pages = resp.json().get("query", {}).get("pages", {})
        result: Set[str] = set()
        for page in pages.values():
            for link in page.get("links", []):
                result.add(link["title"])
        return result
    except Exception:
        return set()


class GraphBuilder:
    async def build(self, article: Article, neighbor_titles: List[str]) -> GraphData:
        origin = article["title"]
        neighbors = neighbor_titles[:40]
        neighbor_set = set(neighbors)

        async with httpx.AsyncClient() as client:
            # Fetch summaries for origin + all neighbors concurrently
            all_titles = [origin] + neighbors
            summary_tasks = [_fetch_summary(client, t) for t in all_titles]

            # Fetch each neighbor's own links concurrently (for cross-edges)
            link_tasks = [_fetch_links(client, t) for t in neighbors]

            summaries, neighbor_links_list = await asyncio.gather(
                asyncio.gather(*summary_tasks),
                asyncio.gather(*link_tasks),
            )

        # Nodes
        nodes = [
            GraphNode(id=t, summary=s)
            for t, s in zip(all_titles, summaries)
        ]

        # Edges: origin → each neighbor
        edges: List[GraphEdge] = [
            GraphEdge(
                source=origin,
                target=n,
                label="links to",
                explanation=f"Wikipedia article on {origin} links to {n}",
            )
            for n in neighbors
        ]

        # Cross-edges: neighbor A → neighbor B if B is in A's link set
        seen: set = set()
        for neighbor, links in zip(neighbors, neighbor_links_list):
            for other in neighbors:
                if other == neighbor:
                    continue
                pair = tuple(sorted([neighbor, other]))
                if pair in seen:
                    continue
                if other in links:
                    seen.add(pair)
                    edges.append(GraphEdge(
                        source=neighbor,
                        target=other,
                        label="links to",
                        explanation=f"{neighbor} links to {other}",
                    ))

        return GraphData(nodes=nodes, edges=edges, origin=origin)
