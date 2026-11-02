"""
Shared guard for every MCP server.

Each MCP server represents a back-end system owned by a different team. They
all trust exactly one caller: the WWT MCP gateway. Every tool call must carry
a short-lived on-behalf-of pass (signed by the gateway) that names:
  - which server it is for (audience)
  - which tool it allows
  - which employee the gateway is acting for, and their role
  - which client the call is bound to
A call without a valid pass — e.g. someone (or some agent) trying to reach
the MCP server directly — is refused.
"""
from jose import JWTError
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from app.identity import verify_obo_token
from app import state


class GatewayPassError(ToolError):
    """Refusal message is returned to the caller (ToolError), not swallowed as a crash."""


def require_gateway_pass(ctx: Context, server: str, tool: str, client_id: str | None = None) -> dict:
    headers = ctx.headers or {}
    auth = headers.get("authorization") or headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise GatewayPassError(
            f"[{server}] Direct access refused: no gateway pass. All calls must go through the WWT MCP gateway."
        )
    try:
        claims = verify_obo_token(auth.removeprefix("Bearer ").strip(), server)
    except JWTError as e:
        raise GatewayPassError(f"[{server}] Gateway pass rejected: {e}")
    if claims.get("tool") != tool:
        raise GatewayPassError(f"[{server}] Gateway pass is for '{claims.get('tool')}', not '{tool}'")
    if client_id is not None and claims.get("client_id") != client_id:
        raise GatewayPassError(f"[{server}] Gateway pass is bound to a different client")
    return claims


def load_client(client_id: str) -> dict:
    c = state.get_client(client_id)
    if not c:
        raise ToolError(f"Unknown client {client_id}")
    return c
