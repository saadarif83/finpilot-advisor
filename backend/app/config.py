"""
All settings come from environment variables (set them in Render's dashboard).
Nothing secret is hard-coded except harmless local-development defaults.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    # Strip whitespace and a trailing slash — the #1 cause of broken deploys.
    return os.getenv(name, default).strip().rstrip("/")


class Settings:
    # ---- Signing secrets -------------------------------------------------
    # Signs employee sign-in tokens (simulated SSO).
    JWT_SECRET: str = _env("JWT_SECRET", "dev-only-jwt-secret-change-me")
    # Signs the short-lived "on-behalf-of" passes the GATEWAY gives to each
    # MCP server. Only the gateway knows it, so nothing can call an MCP server
    # directly without going through the gateway.
    GATEWAY_SIGNING_KEY: str = _env("GATEWAY_SIGNING_KEY", "dev-only-gateway-key-change-me")
    # Signs client approvals and supervisor co-signs (bound to the exact action).
    APPROVAL_SIGNING_KEY: str = _env("APPROVAL_SIGNING_KEY", "dev-only-approval-key-change-me")

    # ---- URLs --------------------------------------------------------------
    FRONTEND_ORIGIN: str = _env("FRONTEND_ORIGIN", "http://localhost:5173")
    PORT: str = _env("PORT", "8000")
    # The backend calling ITSELF (gateway -> MCP servers, copilot -> gateway)
    # always stays on localhost. Never point this at the public Render URL.
    INTERNAL_URL: str = _env("INTERNAL_URL", f"http://127.0.0.1:{_env('PORT', '8000')}")

    # ---- Model lanes ---------------------------------------------------------
    # PRIVATE lane = "inside the perimeter". For this demo it is SIMULATED by a
    # Claude API key; in production point it at an on-prem model server
    # (vLLM / Ollama / OpenShift AI, all OpenAI-compatible) by changing
    # PRIVATE_LANE_PROVIDER=openai, PRIVATE_LANE_BASE_URL and PRIVATE_LANE_MODEL.
    PRIVATE_LANE_PROVIDER: str = _env("PRIVATE_LANE_PROVIDER", "anthropic")  # anthropic | openai | mock
    PRIVATE_LANE_API_KEY: str = _env("PRIVATE_LANE_API_KEY")
    PRIVATE_LANE_BASE_URL: str = _env("PRIVATE_LANE_BASE_URL")  # blank = Anthropic's default
    PRIVATE_LANE_MODEL: str = _env("PRIVATE_LANE_MODEL", "claude-sonnet-5-5")
    PRIVATE_LANE_LABEL: str = _env(
        "PRIVATE_LANE_LABEL",
        "On-prem model (simulated)" if _env("PRIVATE_LANE_PROVIDER", "anthropic") == "anthropic" else "On-prem model",
    )

    # PUBLIC lane = an external model API. Only questions with NO client data
    # may use it; the model gateway enforces that.
    PUBLIC_LANE_PROVIDER: str = _env("PUBLIC_LANE_PROVIDER", "anthropic")
    PUBLIC_LANE_API_KEY: str = _env("PUBLIC_LANE_API_KEY")
    PUBLIC_LANE_BASE_URL: str = _env("PUBLIC_LANE_BASE_URL")
    PUBLIC_LANE_MODEL: str = _env("PUBLIC_LANE_MODEL", "claude-sonnet-5-5")
    PUBLIC_LANE_LABEL: str = _env("PUBLIC_LANE_LABEL", "External model API")

    # ---- Other ---------------------------------------------------------------
    FINNHUB_API_KEY: str = _env("FINNHUB_API_KEY")
    # Actions above this amount need a supervisor co-sign after the client approves.
    COSIGN_THRESHOLD: float = float(_env("COSIGN_THRESHOLD", "5000"))
    # Max gateway tool calls per employee per minute.
    RATE_LIMIT_PER_MIN: int = int(_env("RATE_LIMIT_PER_MIN", "120"))


settings = Settings()
