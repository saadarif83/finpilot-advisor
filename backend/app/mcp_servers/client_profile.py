"""MCP server for the CLIENT PROFILE / KYC system (CRM). Owner: Client Experience."""
from mcp.server.mcpserver import MCPServer, Context
from app.mcp_servers.common import require_gateway_pass, load_client

SERVER = "profile"
mcp = MCPServer(name="wwt-client-profile", instructions="Read-only access to a client's KYC profile, suitability and consents.")


@mcp.tool()
async def get_client_profile(client_id: str, ctx: Context) -> dict:
    """Get the client's profile: segment, risk tolerance, time horizon, liquidity needs, monthly expenses, upcoming needs, goals, KYC status and consents."""
    require_gateway_pass(ctx, SERVER, "get_client_profile", client_id)
    # Returns the full record INCLUDING identifiers (SIN, email, ...). The
    # gateway masks those before any model sees them — the system of record
    # does not need to know or care about AI.
    return {"client_id": client_id, "profile": load_client(client_id)["profile"]}
