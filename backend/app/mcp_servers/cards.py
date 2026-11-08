"""MCP server for the CARD PLATFORM. Owner: Cards."""
from mcp.server.mcpserver import MCPServer, Context
from app.mcp_servers.common import require_gateway_pass, load_client
from app import state

SERVER = "cards"
mcp = MCPServer(name="northstead-card-platform", instructions="Read-only access to a client's credit card at Northstead Financial.")


@mcp.tool()
async def get_card_account(client_id: str, ctx: Context) -> dict:
    """Get the client's credit card: balance, limit, APR, minimum payment and due date."""
    require_gateway_pass(ctx, SERVER, "get_card_account", client_id)
    c = load_client(client_id)
    card = dict(c["card"])
    card["utilization_pct"] = round(100 * card["balance"] / card["credit_limit"], 1)
    return {"client_id": client_id, "card": card}


@mcp.tool()
async def get_card_transactions(client_id: str, ctx: Context) -> dict:
    """Get the client's recent credit card transactions."""
    require_gateway_pass(ctx, SERVER, "get_card_transactions", client_id)
    return {"client_id": client_id, "transactions": load_client(client_id)["card_transactions"]}


@mcp.tool()
async def get_spending_breakdown(client_id: str, ctx: Context) -> dict:
    """Get the client's card spending this month, totalled by category."""
    require_gateway_pass(ctx, SERVER, "get_spending_breakdown", client_id)
    return {"client_id": client_id, "month": "2026-10", "categories": state.spending_by_category(load_client(client_id))}
