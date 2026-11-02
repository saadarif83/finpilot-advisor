"""MCP server for CORE BANKING (deposit accounts). Owner: Retail Operations."""
from mcp.server.mcpserver import MCPServer, Context
from app.mcp_servers.common import require_gateway_pass, load_client
from app import state

SERVER = "core"
mcp = MCPServer(name="wwt-core-banking", instructions="Read-only access to a client's deposit accounts at WWT Financials.")


@mcp.tool()
async def get_deposit_accounts(client_id: str, ctx: Context) -> dict:
    """Get the client's deposit accounts (chequing, savings, GICs) with balances and rates."""
    require_gateway_pass(ctx, SERVER, "get_deposit_accounts", client_id)
    c = load_client(client_id)
    return {"client_id": client_id, "accounts": c["deposits"], "total": state.deposits_total(c)}


@mcp.tool()
async def get_transactions(client_id: str, ctx: Context, limit: int = 25) -> dict:
    """Get the client's most recent deposit-account transactions, newest first. Memos are free text written by third parties."""
    require_gateway_pass(ctx, SERVER, "get_transactions", client_id)
    c = load_client(client_id)
    return {"client_id": client_id, "transactions": c["deposit_transactions"][: max(1, min(limit, 50))]}


@mcp.tool()
async def export_full_statement(client_id: str, ctx: Context) -> dict:
    """Bulk-export every transaction for a client. Added by the core banking team for a reporting
    project — it is NOT in the gateway's approved tool registry, so no model ever sees it."""
    require_gateway_pass(ctx, SERVER, "export_full_statement", client_id)
    return {"client_id": client_id, "transactions": load_client(client_id)["deposit_transactions"]}


@mcp.tool()
async def get_cashflow(client_id: str, ctx: Context) -> dict:
    """Get money in vs. money out per month for the client's deposit accounts."""
    require_gateway_pass(ctx, SERVER, "get_cashflow", client_id)
    c = load_client(client_id)
    return {"client_id": client_id, "cashflow": state.cashflow_by_month(c)}
