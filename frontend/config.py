import logging
import os
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("devops_monitor.frontend")

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


def _is_valid_api_base(url: str) -> bool:
    """Only absolute http(s) URLs pointing away from this app's origin qualify.

    The frontend runs on Streamlit (Community Cloud or a local server) and talks
    to the FastAPI backend over the network. It must NEVER send API requests to
    its own origin (e.g. ``https://<app>.streamlit.app/api/...`` -> 404) or use
    relative paths, which is what produced the stale ``/api/v2/user/details``
    404 in production.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host == "streamlit.app" or host.endswith(".streamlit.app"):
        return False
    return True


def _candidate_api_urls():
    """Yield (source, value) pairs in precedence order."""
    secret_value = _secrets_api_url()
    if secret_value:
        yield "Streamlit secret API_URL", secret_value
    env_value = os.getenv("API_URL")
    if env_value:
        yield "environment API_URL", env_value
    yield "default", _PRODUCTION_API_URL


def _resolve_api_url():
    """Resolve the API base URL.

    Precedence:
      1. Streamlit Cloud secret ``API_URL`` (st.secrets) — production deployments.
      2. Environment variable ``API_URL`` — docker-compose / shell / frontend/.env.
      3. Production backend default — keeps the public deployment working out
         of the box.

    Every candidate is validated: it must be an absolute http(s) URL and must
    not point at the Streamlit origin. Invalid values are ignored (with a
    warning that never includes secret material) so all API requests always
    resolve to the configured backend (frontend/api/client.py builds every
    request as f"{API_URL}{path}" from this single base).
    """
    for source, value in _candidate_api_urls():
        candidate = value.strip().rstrip("/")
        if _is_valid_api_base(candidate):
            return candidate
        if source != "default":
            logger.warning(
                "Ignoring %s: API base must be an absolute http(s) URL and must "
                "not point at the Streamlit origin; falling back to the "
                "production backend.",
                source,
            )
    return _PRODUCTION_API_URL


API_URL = _resolve_api_url()


