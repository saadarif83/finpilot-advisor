"""MCP server for RESEARCH: market news, product rates, internal policy search.
Contains NO client data, so it is the only server the external model lane may use.
Owner: Investment Research / Compliance."""
import httpx
from mcp.server.mcpserver import MCPServer, Context
from app.mcp_servers.common import require_gateway_pass
from app.config import settings
from app.data_seed import PRODUCTS, POLICIES

SERVER = "research"
mcp = MCPServer(name="northstead-research", instructions="Market news, current product rates and internal policy search. No client data.")

SAMPLE_NEWS = [
    "Bank of Canada holds overnight rate, signals patience on further cuts",
    "Canadian 5-year bond yields edge lower ahead of jobs data",
    "TSX rises as energy and financials lead gains",
    "GIC rates drift lower as lenders price in a slower rate path",
    "Housing resales in Toronto tick up for third straight month",
]


@mcp.tool()
async def get_market_news(ctx: Context, topic: str = "Canadian markets") -> dict:
    """Get recent market news headlines (rates, markets, housing)."""
    require_gateway_pass(ctx, SERVER, "get_market_news")
    if settings.FINNHUB_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get("https://finnhub.io/api/v1/news", params={"category": "general", "token": settings.FINNHUB_API_KEY})
            if r.status_code == 200:
                return {"topic": topic, "source": "Finnhub (live)", "headlines": [i.get("headline") for i in r.json()[:6]]}
        except httpx.HTTPError:
            pass
    return {"topic": topic, "source": "Sample headlines (no FINNHUB_API_KEY set)", "headlines": SAMPLE_NEWS}


@mcp.tool()
async def get_product_rates(ctx: Context) -> dict:
    """Get Northstead Financial's current GIC and savings rates and the prime rate."""
    require_gateway_pass(ctx, SERVER, "get_product_rates")
    return PRODUCTS


@mcp.tool()
async def search_policies(query: str, ctx: Context) -> dict:
    """Search Northstead Financial's internal advice and AI-use policies (prepayment, suitability, card debt, AI use, untrusted content)."""
    require_gateway_pass(ctx, SERVER, "search_policies")
    words = [w for w in query.lower().split() if len(w) > 2]
    scored = []
    for p in POLICIES:
        hay = (p["title"] + " " + p["text"]).lower()
        score = sum(hay.count(w) for w in words)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda s: -s[0])
    hits = [p for _, p in scored[:3]] or POLICIES[:2]
    return {"query": query, "results": hits}
