"""
Northstead Financial — Advisor Copilot backend.

One FastAPI service (Render) that hosts, for the demo:
  /auth        simulated enterprise SSO
  /workspace   screen data for the advisor app
  /copilot     the AI agent (streams events)
  /gateway     the MCP gateway + model gateway (in production: separate services)
  /mcp/<name>  seven MCP servers, one per back-end system
  /proposals, /client-approval   human approvals; the executor behind them
  /audit       evidence records
"""
from contextlib import asynccontextmanager, AsyncExitStack
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.identity import current_employee
from app import state, audit
from app.gateway import events
from app.gateway.tool_gateway import router as gateway_router, discover_tools, _discovered
from app.proposals import store as proposal_store
from app.proposals.router import router as proposals_router
from app.copilot.router import router as copilot_router
from app.workspace import router as workspace_router
from app.auth_router import router as auth_router
from app.audit_router import router as audit_router
from app.mcp_servers import core_banking, cards, mortgage, wealth, client_profile, research, advice

MCP_APPS = {
    "core": core_banking.mcp,
    "cards": cards.mcp,
    "mortgage": mortgage.mcp,
    "wealth": wealth.mcp,
    "profile": client_profile.mcp,
    "research": research.mcp,
    "advice": advice.mcp,
}
_mounted = {name: srv.streamable_http_app(streamable_http_path="/", stateless_http=True, json_response=True)
            for name, srv in MCP_APPS.items()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Each mounted MCP app has its own session manager that must be started
    # explicitly — FastAPI does not run a mounted sub-app's lifespan.
    async with AsyncExitStack() as stack:
        for sub in _mounted.values():
            await stack.enter_async_context(sub.router.lifespan_context(sub))
        yield


app = FastAPI(title="Northstead Financial Advisor Copilot", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth_router, workspace_router, copilot_router, gateway_router, proposals_router, audit_router):
    app.include_router(r)
for name, sub in _mounted.items():
    app.mount(f"/mcp/{name}", sub)


@app.get("/")
def health():
    return {"status": "ok", "service": "northstead-advisor-copilot"}


@app.post("/admin/reset")
async def reset_demo(employee: dict = Depends(current_employee)):
    """Put every client, proposal, audit record and counter back to the start."""
    state.reset_state()
    proposal_store.reset()
    audit.reset()
    events.reset()
    _discovered.clear()
    await discover_tools(force=True)
    events.record("admin", "info", employee=employee, detail="Demo reset to starting data")
    return {"reset": True}
