"""MCP server for the WEALTH PLATFORM (TFSA, RRSP, RESP). Owner: Wealth Management."""
from mcp.server.mcpserver import MCPServer, Context
from app.mcp_servers.common import require_gateway_pass, load_client
from app import state
from app.data_seed import PERFORMANCE_MONTHS

SERVER = "wealth"
mcp = MCPServer(name="wwt-wealth-platform", instructions="Read-only access to a client's investment accounts at WWT Financials.")


@mcp.tool()
async def get_holdings(client_id: str, ctx: Context) -> dict:
    """Get the client's investment holdings across registered accounts, with market values."""
    require_gateway_pass(ctx, SERVER, "get_holdings", client_id)
    c = load_client(client_id)
    holdings = [{**h, "market_value": round(h["units"] * h["price"], 2)} for h in c["wealth"]["holdings"]]
    return {"client_id": client_id, "holdings": holdings, "holdings_value": state.wealth_holdings_value(c)}


@mcp.tool()
async def get_wealth_cash(client_id: str, ctx: Context) -> dict:
    """Get uninvested cash sitting in each of the client's investment accounts."""
    require_gateway_pass(ctx, SERVER, "get_wealth_cash", client_id)
    c = load_client(client_id)
    return {"client_id": client_id, "accounts": c["wealth"]["accounts"], "total_cash": state.wealth_cash(c)}


@mcp.tool()
async def get_performance(client_id: str, ctx: Context) -> dict:
    """Get the client's total investment value at each of the last six month-ends."""
    require_gateway_pass(ctx, SERVER, "get_performance", client_id)
    c = load_client(client_id)
    return {"client_id": client_id, "history": [{"month": m, "value": v} for m, v in zip(PERFORMANCE_MONTHS, c["wealth"]["performance"])]}
