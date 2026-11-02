"""MCP server for MORTGAGE SERVICING. Owner: Lending."""
from mcp.server.mcpserver import MCPServer, Context
from app.mcp_servers.common import require_gateway_pass, load_client
from app import state

SERVER = "mortgage"
mcp = MCPServer(name="wwt-mortgage-servicing", instructions="Read-only access to a client's mortgage at WWT Financials.")


@mcp.tool()
async def get_mortgage(client_id: str, ctx: Context) -> dict:
    """Get the client's mortgage: balance, rate, term, payment, and this year's lump-sum prepayment privilege (used and remaining)."""
    require_gateway_pass(ctx, SERVER, "get_mortgage", client_id)
    m = load_client(client_id)["mortgage"]
    if not m:
        return {"client_id": client_id, "mortgage": None, "note": "Client has no mortgage with WWT Financials."}
    return {"client_id": client_id, "mortgage": m, "prepayment_privilege": state.mortgage_privilege(m)}
