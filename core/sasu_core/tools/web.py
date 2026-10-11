from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import httpx

from .registry import ToolContext, ToolResult, obj, tool


@tool("web_open", "Open a web page in the default browser.", obj(["url"], url={"type": "string"}))
async def web_open(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    url = str(args["url"]).strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url) and not url.lower().startswith(
        ("http://", "https://")
    ):
        return ToolResult(False, "Only web links can be opened")  # file:, javascript:, x-apple…
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or ("." not in host and host != "localhost")
    ):
        return ToolResult(False, "Only web links can be opened")
    p = await ctx.run(["open", url])
    return ToolResult(p.ok, f"Opened {parsed.netloc}")


def _clean(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def parse_ddg(page: str, limit: int = 6) -> list[tuple[str, str, str]]:
    """(title, url, snippet) from DuckDuckGo's HTML results page."""
    results = []
    for m in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>',
        page,
        re.S,
    ):
        href = html.unescape(m.group(1))
        target = parse_qs(urlparse(href).query).get("uddg", [href])[0]
        results.append((_clean(m.group(2)), unquote(target), _clean(m.group(3))))
        if len(results) >= limit:
            break
    return results


@tool(
    "web_search",
    "Search the web and read the top results (titles, links, snippets).",
    obj(["query"], query={"type": "string"}),
    untrusted_output=True,
)
async def web_search(args: dict[str, Any], ctx: ToolContext) -> ToolResult:
    q = str(args["query"])
    try:
        async with httpx.AsyncClient(
            timeout=10, headers={"User-Agent": "Mozilla/5.0 Sasu"}
        ) as client:
            r = await client.get(f"https://html.duckduckgo.com/html/?q={quote_plus(q)}")
        results = parse_ddg(r.text)
    except httpx.HTTPError:
        results = []
    if not results:
        await ctx.run(["open", f"https://www.google.com/search?q={quote_plus(q)}"])
        return ToolResult(True, "Opened a search in your browser")
    body = "\n\n".join(f"{t}\n{u}\n{s}" for t, u, s in results)
    return ToolResult(True, f"{len(results)} results", body)
