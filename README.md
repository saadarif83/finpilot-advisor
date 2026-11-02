# WWT Financials — Advisor Copilot (WWT AI Days demo)

A browser-based **advisor copilot** for a fictional bank, built to show what it takes for a
regulated organization to let an AI agent work on its core systems:

- **MCP** as the standard way the agent reaches each back-end system (one MCP server per system)
- a **governing gateway** that every model and tool call passes through
- **read / act separation**: the AI can read and propose, only humans approve, only a deterministic executor moves money
- **model lanes**: client data stays on the private (in-perimeter) lane; the external lane gets general research only
- an **audit record** for every AI-assisted request

Everything (bank, clients, numbers) is fictional.

---

## Honest-demo notes (say these out loud, and show them in the deck)

| In this demo | In production |
|---|---|
| **Private lane = a Claude API key** standing in for an on-prem model. Counted as 0 B egress. | A model served inside the perimeter (vLLM, Ollama, Red Hat OpenShift AI, NVIDIA NIM…). Switch by setting `PRIVATE_LANE_PROVIDER=openai`, `PRIVATE_LANE_BASE_URL`, `PRIVATE_LANE_MODEL` — no code change. |
| **Gateway runs inside the same FastAPI process** (`/gateway`), and the MCP servers are mounted in that process too (`/mcp/<name>`). | Gateway is its own independently operated service; each MCP server is run by the team that owns that system. |
| Employee sign-in is a **simulated SSO** (built-in token issuer). | The bank's IdP (Entra ID, Okta, Keycloak…) with MFA. |
| State, audit log and events are **in memory** (reset on restart or with **Reset demo**). | Systems of record + append-only (WORM) audit storage. |
| Policy is a readable Python file (`backend/app/policy.py`). | A policy engine (e.g. OPA) with versioned policies. |

---

## Architecture

```
Browser (advisor)                     Phone (client)
   │  employee token                     │  one-time approval link
   ▼                                     ▼
/copilot  ── agent loop ──►  MODEL GATEWAY  ── private lane ─► "on-prem" model (simulated)
   │                         (lane routing,  └─ public lane ──► external model API (data guard)
   │                          data guard,
   │                          egress meter)
   ▼
TOOL GATEWAY  /gateway  (role policy · approved registry · client binding · consent ·
   │                     on-behalf-of pass · PII masking · injection scan · proposal freeze · events)
   ▼  60-second on-behalf-of pass per call (RFC 8693-style)
MCP servers  /mcp/core  /mcp/cards  /mcp/mortgage  /mcp/wealth  /mcp/profile  /mcp/research  /mcp/advice
                                                                                  │ (propose only)
APPROVALS  /proposals, /client-approval  ── client signs ─► supervisor co-signs (> $5,000)
   ▼
DETERMINISTIC EXECUTOR (no MCP tool, no model access) ── two ledger writes + compensation
   ▼
AUDIT  /audit   ·   GOVERNANCE CONSOLE (live gateway decisions, egress, kill switch)
```

### Repo layout

```
backend/                     FastAPI service → Render
  app/main.py                mounts everything
  app/config.py              all settings (environment variables)
  app/policy.py              THE policy: tool registry, role access, consent, masking, injection patterns
  app/identity.py            simulated SSO, on-behalf-of passes, client approval links
  app/data_seed.py           5 fictional clients, products, internal policies
  app/state.py               live in-memory "systems of record" + ledger write functions
  app/mcp_servers/           7 MCP servers (one per back-end system); each refuses calls without a gateway pass
  app/gateway/tool_gateway.py   the MCP gateway
  app/gateway/model_gateway.py  the model gateway (lanes, data guard, egress, providers)
  app/gateway/mock_model.py     scripted model for testing without an API key (never on stage)
  app/copilot/               the agent loop + streaming endpoint
  app/proposals/             proposal store (hash-bound), approvals API, deterministic executor
  app/audit.py               evidence records
frontend/                    React (Vite) app → Vercel
  src/pages/                 Login, Clients, ClientWorkspace, Research, Approvals, Governance, Audit, ApprovePage (phone)
  src/components/            Copilot, ActivityFeed, ProposalCard, QrModal, Charts, Shell
  src/theme.css              all colours in one place
```

---

## Demo clients and what each one shows

| Client | Try asking | What the audience sees |
|---|---|---|
| **Aisha Rahman** | "Should Aisha pay down her Visa?" | Tools called, identifiers masked, a $4,812 proposal → client approves on phone → executes (under the co-sign threshold). |
| **Daniel Okafor** | "Review Daniel's recent account activity." | An e-Transfer memo contains a hidden instruction to transfer $10,000. Gateway **flags** it; the model has no tool that could move money; it warns the advisor. |
| **Daniel Okafor** | "Could he earn more in a GIC without hurting his renovation plans?" | Suitability: keeps a 3-month buffer and reserves the $25,000 renovation, proposes $57,000 in a 1-year GIC → needs supervisor co-sign. |
| **Mei Lin Chen** | "Her card balance is high — best way to bring it down?" | Uses TFSA cash (RRSP excluded for tax), $7,800 → client + supervisor. |
| **Robert & Linda Tremblay** | "They'd like to prepay $40,000 — can they?" | Capped at $17,000 by the annual prepayment privilege (policy POL-ADV-014). |
| **Marco Silva** | "Full picture including investments." | Client withheld consent for AI use of wealth data → wealth tools hidden/denied, even though the advisor can see it on screen. |
| **Sam Patel (Teller)** | "How is Aisha's portfolio doing?" | 9 tools hidden by role; mortgage and investments show 🔒 on screen. |
| **Research page** | the third suggestion (mentions Daniel by name) | **Data guard** blocks the external-lane call before anything leaves; "Re-run on private lane". |
| **Approvals page** | "⚠ Simulate tampering" on a proposal awaiting co-sign, then co-sign | Executor **refuses**: parameters no longer match the hash the client signed. |
| **Governance console** | "Attempt direct MCP access"; flip the kill switch | Direct calls to an MCP server are refused (no pass / forged pass). Kill switch stops all AI instantly. |

**Supervisor co-sign:** open a second browser tab, **Switch user → Morgan Wright**. Each tab keeps its own sign-in.

---

## Running locally (optional)

```bash
cd backend
pip install -r requirements.txt
PRIVATE_LANE_PROVIDER=mock PUBLIC_LANE_PROVIDER=mock uvicorn app.main:app --port 8000   # no API key needed
cd ../frontend
npm install
npm run dev     # http://localhost:5173
```

Deploying: see **DEPLOY.md**.
