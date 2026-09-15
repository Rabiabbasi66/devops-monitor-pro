import os

from dotenv import load_dotenv

load_dotenv()

# Production FastAPI backend (never localhost, never this app's own origin).
_PRODUCTION_API_URL = "https://devops-monitor-pro.vercel.app/api"


def _secrets_api_url():
    """Read API_URL from Streamlit secrets (Streamlit Community Cloud).

    Cloud Secrets are exposed through ``st.secrets`` only — they are NOT
    injected into the process environment, so ``os.getenv`` can never see
    them. Every lookup is wrapped so this module stays importable outside a
    Streamlit runtime (local scripts, tooling, CI) where no secrets exist.
    """
    try:
        import streamlit as st

        if "API_URL" in st.secrets:
            return str(st.secrets["API_URL"]).strip()
    except Exception:
        # No Streamlit runtime or no secrets configured (local dev, CI, tools).
        pass
    return None


def _resolve_api_url():
    """Resolve the API base URL.

    Precedence:
      1. Streamlit Cloud secret ``API_URL`` (st.secrets) — production deployments.
      2. Environment variable ``API_URL`` — docker-compose / shell / frontend/.env.
      3. Production backend default — keeps the public deployment working out
         of the box.

    All API requests (frontend/api/client.py) are built from this single base,
    so they always target the configured backend origin.
    """
    api_url = _secrets_api_url() or os.getenv("API_URL") or _PRODUCTION_API_URL
    # The client builds URLs as f"{API_URL}{path}"; normalize a trailing slash
    # out of the configured value so we never emit "//" path segments.
    return api_url.strip().rstrip("/")


API_URL = _resolve_api_url()

