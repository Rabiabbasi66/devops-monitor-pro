"""Shared runtime for the DevOps Monitor Pro agent.

This module centralises the pieces that both entrypoints need:

  - the enrollment client (exchanges a one-time enrollment code for permanent
    credentials via the existing ``POST /api/agents/enroll`` endpoint),
  - the monitoring loop (collect metrics with psutil, POST them with the
    permanent ``X-Agent-Token``, retry and reconnect automatically),
  - status callbacks used by the GUI and Windows service to surface progress
    to the end user.

The permanent agent token is only ever held in memory and in the local
credential file; it is never logged.
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

import requests

from config import settings
from collectors import (
    collect_cpu,
    collect_disk,
    collect_memory,
    collect_network,
    collect_processes,
    collect_system,
)
from credentials_file import load_credentials, save_credentials

logger = logging.getLogger("monitoring-agent")

AGENT_VERSION = "2.1.0"

DEFAULT_INTERVAL_SECONDS = 30
CONNECT_TIMEOUT = 10
REQUEST_TIMEOUT = 15
ENROLL_TIMEOUT = 30

StatusCallback = Optional[Callable[[str], None]]


class EnrollmentError(Exception):
    """Raised when enrollment fails; ``message`` is safe to show to users."""

    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


def _log(message: str, status_cb: StatusCallback = None, level: int = logging.INFO) -> None:
    logger.log(level, message)
    if status_cb:
        try:
            status_cb(message)
        except Exception:  # noqa: BLE001 - callbacks must never break the loop
            pass


def enroll_agent(enrollment_code: str, api_url: Optional[str] = None,
                 status_cb: StatusCallback = None) -> Dict[str, Any]:
    """Exchange a one-time enrollment code for permanent agent credentials.

    Uses the existing backend endpoint ``POST /api/agents/enroll`` (short-lived,
    single-use, SHA-256-hashed enrollment tokens). On success the credentials
    are saved to the local credential file and returned.
    """
    base = (api_url or settings.API_URL).rstrip("/")
    url = f"{base}/agents/enroll"

    _log("Connecting to the monitoring platform...", status_cb)
    try:
        response = requests.post(
            url,
            json={"enrollment_token": enrollment_code},
            timeout=ENROLL_TIMEOUT,
        )
    except requests.exceptions.SSLError as exc:
        raise EnrollmentError(
            "Secure connection failed (SSL). Verify the API URL uses HTTPS.",
            detail=str(exc),
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise EnrollmentError(
            "Could not reach the monitoring platform. Check your internet connection and try again.",
            detail=str(exc),
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise EnrollmentError("The server took too long to respond. Try again.", detail=str(exc)) from exc

    if response.status_code == 200:
        try:
            data = response.json()
        except ValueError as exc:
            raise EnrollmentError("The server returned an unexpected response.", detail=str(exc)) from exc
        config = {
            "server_id": data["server_id"],
            "agent_token": data["agent_token"],
            "api_url": base,
            "interval_seconds": int(data.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)),
            "enrolled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        save_credentials(config)
        _log("Agent enrolled successfully.", status_cb)
        return config

    detail = ""
    try:
        body = response.json()
        detail = str(body.get("detail", "")) if isinstance(body, dict) else ""
    except ValueError:
        pass

    if response.status_code in (400, 401):
        if "expired" in detail.lower():
            message = "This enrollment code has expired. Generate a new one in the dashboard."
        else:
            message = "Invalid or already-used enrollment code. Generate a new one in the dashboard."
    elif response.status_code == 404:
        message = "The server linked to this enrollment code was removed. Add the server again."
    elif response.status_code == 429:
        message = "Too many attempts. Please wait a few minutes and try again."
    else:
        message = f"Enrollment failed (server error {response.status_code})."

    _log(f"Enrollment failed: HTTP {response.status_code}", status_cb, logging.ERROR)
    raise EnrollmentError(message, detail=detail)


def load_or_none() -> Optional[Dict[str, Any]]:
    """Load stored credentials (None when not enrolled)."""
    return load_credentials()


def collect_all() -> Dict[str, Any]:
    """Collect all metrics from all collectors."""
    cpu = collect_cpu()
    memory = collect_memory()
    disk = collect_disk()
    network = collect_network()
    system = collect_system()
    processes = collect_processes()

    return {
        "server_id": settings.SERVER_ID,
        "agent_version": AGENT_VERSION,
        **cpu,
        **memory,
        **disk,
        **network,
        **system,
        "processes": processes,
    }


def send_metrics(payload: Dict[str, Any], api_url: str, agent_token: str) -> bool:
    """Send metrics to the backend with retry logic. Never logs the token."""
    url = f"{api_url.rstrip('/')}/monitoring/metrics"
    headers = {"X-Agent-Token": agent_token, "Content-Type": "application/json"}

    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                logger.info("Metrics sent successfully")
                return True
            if response.status_code == 401:
                logger.error("Invalid agent token - authentication failed")
                return False
            logger.warning(
                "Failed to send metrics (attempt %d/%d): HTTP %s",
                attempt + 1, max_retries, response.status_code,
            )
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except requests.exceptions.Timeout:
            logger.warning("Timeout sending metrics (attempt %d/%d)", attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except requests.exceptions.ConnectionError:
            logger.warning("Connection error sending metrics (attempt %d/%d)", attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error sending metrics: %s", exc)
            return False

    logger.error("Failed to send metrics after %d retries", max_retries)
    return False


class MonitoringLoop(threading.Thread):
    """Continuous monitoring loop with automatic reconnection.

    Sends metrics every ``interval`` seconds. On connection errors it retries
    with capped exponential backoff so a temporarily unavailable backend does
    not lose the agent permanently. Stop with ``stop()`` (the service uses this
    on shutdown).
    """

    def __init__(self, server_id: str, agent_token: str, api_url: str,
                 interval: int = DEFAULT_INTERVAL_SECONDS,
                 status_cb: StatusCallback = None):
        super().__init__(name="monitoring-loop", daemon=True)
        self.server_id = server_id
        self.agent_token = agent_token
        self.api_url = api_url.rstrip("/")
        self.interval = max(5, int(interval))
        self.status_cb = status_cb
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        _log(
            f"Monitoring started — sending metrics every {self.interval}s "
            f"(server {self.server_id}).",
            self.status_cb,
        )
        backoff = 0
        while not self._stop_event.is_set():
            started = time.monotonic()
            try:
                payload = collect_all()
                payload["server_id"] = self.server_id
                ok = send_metrics(payload, self.api_url, self.agent_token)
                if ok:
                    backoff = 0
                else:
                    backoff = min(backoff + 1, 6)
            except Exception:  # noqa: BLE001 - the loop must survive anything
                logger.exception("Agent loop error")
                backoff = min(backoff + 1, 6)

            delay = self.interval
            if backoff:
                delay = min(self.interval * (2 ** backoff), 600)
                _log(
                    f"Connection issue — retrying in {int(delay)}s...",
                    self.status_cb,
                    logging.WARNING,
                )

            # Sleep in small slices so stop() reacts quickly.
            slept = 0.0
            while slept < delay and not self._stop_event.is_set():
                self._stop_event.wait(min(1.0, delay - slept))
                slept += 1.0
