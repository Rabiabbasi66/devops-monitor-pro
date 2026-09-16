import os

from dotenv import load_dotenv

load_dotenv()

# Production FastAPI backend (never localhost, never this app's own origin).
_PRODUCTION_API_URL = "https://devops-monitor-pro.vercel.app/api"


def _secrets_api_url():
    
    try:
        import streamlit as st

        if "API_URL" in st.secrets:
            return str(st.secrets["API_URL"]).strip()
    except Exception:
        # No Streamlit runtime or no secrets configured (local dev, CI, tools).
        pass
    return None


def _resolve_api_url():
    
    api_url = _secrets_api_url() or os.getenv("API_URL") or _PRODUCTION_API_URL
    # The client builds URLs as f"{API_URL}{path}"; normalize a trailing slash
    # out of the configured value so we never emit "//" path segments.
    return api_url.strip().rstrip("/")


API_URL = _resolve_api_url()

