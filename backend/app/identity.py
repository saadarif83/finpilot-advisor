"""
SIMULATED enterprise identity.

In production this is the bank's IdP (Entra ID, Okta, Keycloak/Red Hat build
of Keycloak, PingFederate...) issuing OIDC tokens after employee SSO + MFA.
Here a tiny built-in "IdP" signs the same kind of token so the demo can't
break on stage. Everything downstream (gateway, MCP servers) treats it like
a real OIDC access token: it reads the subject and role claims.

Three kinds of token exist in this app:
  1. Employee token  - who is at the keyboard (sub, name, role).
  2. On-behalf-of    - minted by the GATEWAY per tool call: "the gateway, acting
     pass                for employee X, on client Y, may call tool Z, for 60s".
                         Modelled on OAuth 2.0 Token Exchange (RFC 8693).
  3. Client approval - a link token the client uses on their phone to approve
     token               one specific proposal (bound to that proposal's hash).
"""
import time
import uuid
from fastapi import Header, HTTPException
from jose import jwt, JWTError
from app.config import settings

ALG = "HS256"
ISSUER = "https://sso.northstead.example/simulated"

EMPLOYEES = {
    "jordan.lee": {"username": "jordan.lee", "name": "Jordan Lee", "role": "advisor", "title": "Wealth Advisor", "branch": "Toronto — King & Bay"},
    "sam.patel": {"username": "sam.patel", "name": "Sam Patel", "role": "teller", "title": "Customer Service Representative", "branch": "Toronto — King & Bay"},
    "morgan.wright": {"username": "morgan.wright", "name": "Morgan Wright", "role": "supervisor", "title": "Branch Manager", "branch": "Toronto — King & Bay"},
    "taylor.brooks": {"username": "taylor.brooks", "name": "Taylor Brooks", "role": "compliance", "title": "Compliance Officer", "branch": "Head Office"},
}

DEMO_PASSWORD = "demo123"


# ------------------------------------------------------------ employee tokens

def issue_employee_token(username: str) -> str:
    e = EMPLOYEES[username]
    now = int(time.time())
    return jwt.encode(
        {"iss": ISSUER, "aud": "northstead-advisor-app", "sub": e["username"], "name": e["name"],
         "role": e["role"], "iat": now, "exp": now + 12 * 3600, "jti": str(uuid.uuid4())},
        settings.JWT_SECRET, algorithm=ALG,
    )


def decode_employee_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALG], audience="northstead-advisor-app", issuer=ISSUER)
    except JWTError:
        raise HTTPException(401, "Invalid or expired sign-in. Please sign in again.")


def current_employee(authorization: str = Header(None)) -> dict:
    """FastAPI dependency: the signed-in employee, from the Bearer token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not signed in")
    claims = decode_employee_token(authorization.removeprefix("Bearer ").strip())
    emp = EMPLOYEES.get(claims["sub"])
    if not emp:
        raise HTTPException(401, "Unknown employee")
    return {**emp, "token": authorization.removeprefix("Bearer ").strip()}


def require_role(emp: dict, *roles: str):
    if emp["role"] not in roles:
        raise HTTPException(403, f"This action requires role: {', '.join(roles)}")


# ------------------------------------------------- gateway on-behalf-of passes

def mint_obo_token(*, server: str, tool: str, employee: dict, client_id: str | None,
                   domains: list[str], request_id: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": "northstead-mcp-gateway",
            "aud": f"mcp:{server}",
            "sub": employee["username"],
            "role": employee["role"],
            "act": {"sub": "northstead-mcp-gateway"},  # RFC 8693 "actor" claim
            "client_id": client_id,
            "tool": tool,
            "domains": domains,
            "request_id": request_id,
            "iat": now,
            "exp": now + 60,
        },
        settings.GATEWAY_SIGNING_KEY, algorithm=ALG,
    )


def verify_obo_token(token: str, server: str) -> dict:
    return jwt.decode(token, settings.GATEWAY_SIGNING_KEY, algorithms=[ALG],
                      audience=f"mcp:{server}", issuer="northstead-mcp-gateway")


# ------------------------------------------------------- client approval links

def issue_client_approval_token(proposal_id: str, client_id: str, args_hash: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"iss": "northstead-approvals", "aud": "client-approval", "sub": client_id, "proposal_id": proposal_id,
         "args_hash": args_hash, "iat": now, "exp": now + 3600},
        settings.APPROVAL_SIGNING_KEY, algorithm=ALG,
    )


def verify_client_approval_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.APPROVAL_SIGNING_KEY, algorithms=[ALG], audience="client-approval", issuer="northstead-approvals")
    except JWTError:
        raise HTTPException(401, "This approval link is invalid or has expired.")
