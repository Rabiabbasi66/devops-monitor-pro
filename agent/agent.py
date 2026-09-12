"""DevOps Monitor Pro agent — command-line entrypoint.

Development / server mode (unchanged behaviour):

    python agent.py                # run monitoring with existing config/env
    python agent.py --enroll "TOKEN"

Client mode (packaged Windows agent):

    DevOpsMonitorAgent.exe --enroll "TOKEN"     # enroll + start monitoring
    DevOpsMonitorAgent.exe --tray               # start monitoring silently
    DevOpsMonitorAgent.exe                      # opens the enrollment GUI window

After enrollment, credentials are stored locally (see ``credentials_file.py``);
the agent never needs SERVER_ID/AGENT_TOKEN env vars or a .env file.
"""

import argparse
import logging
import os
import sys
import time

from config import settings
from runtime import (
    DEFAULT_INTERVAL_SECONDS,
    collect_all,
    enroll_agent,
    send_metrics,
)

logger = logging.getLogger("monitoring-agent")


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _is_windows() -> bool:
    return os.name == "nt"


def _resolve_runtime_mode(args) -> str:
    """Decide the runtime mode from CLI args and packaging state.

    Modes: ``gui`` (tkinter enrollment window), ``tray`` (headless background
    monitoring), ``console`` (classic CLI loop for development/servers).
    """
    if args.gui:
        return "gui"
    if args.tray:
        return "tray"
    if _is_frozen() and _is_windows() and not args.enroll and not args.console:
        # Default for the packaged Windows agent: launch the client GUI.
        return "gui"
    return "console"


# ---------------------------------------------------------------------------
# Enrollment helpers (kept for backward compatibility with existing scripts)
# ---------------------------------------------------------------------------


def load_config():
    """Load stored agent configuration from the credential file (or None)."""
    from credentials_file import load_credentials

    return load_credentials()


def save_config(config):
    """Persist agent credentials to the secure local credential file."""
    from credentials_file import save_credentials

    save_credentials(config)


# ---------------------------------------------------------------------------
# Console monitoring loop (development / Docker / servers)
# ---------------------------------------------------------------------------


def run_console_loop(server_id: str, agent_token: str, api_url: str, interval: int) -> None:
    logger.info("Starting monitoring agent for server %s", server_id)
    while True:
        try:
            payload = collect_all()
            payload["server_id"] = server_id
            send_metrics(payload, api_url, agent_token)
        except Exception:
            logger.exception("Agent loop error")
        time.sleep(interval)


def run_console_mode(args) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if args.enroll:
        config = enroll_agent(args.enroll)
        server_id = config["server_id"]
        agent_token = config["agent_token"]
        api_url = config["api_url"]
        interval = config.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)
    else:
        config = load_config()
        if config:
            server_id = config["server_id"]
            agent_token = config["agent_token"]
            api_url = config["api_url"]
            interval = config.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)
        elif settings.SERVER_ID and settings.AGENT_TOKEN:
            # Environment / .env based configuration (Docker & CI workflows).
            server_id = settings.SERVER_ID
            agent_token = settings.AGENT_TOKEN
            api_url = settings.API_URL
            interval = settings.INTERVAL_SECONDS
        else:
            raise SystemExit(
                "Not enrolled yet. Provide an enrollment code:\n"
                '  DevOpsMonitorAgent.exe --enroll "TOKEN"\n'
                "or set SERVER_ID and AGENT_TOKEN in agent/.env."
            )

    run_console_loop(server_id, agent_token, api_url, interval)
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="DevOps Monitor Pro Agent")
    parser.add_argument("--enroll", help="Enrollment token for automatic agent setup")
    parser.add_argument("--gui", action="store_true", help="Open the enrollment GUI window")
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Run monitoring in the background without a window",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Force the classic console mode (development/servers)",
    )
    args = parser.parse_args()

    mode = _resolve_runtime_mode(args)

    if mode == "gui":
        import gui

        return gui.main()

    if mode == "tray":
        return _run_tray()

    return run_console_mode(args)


def _run_tray() -> int:
    """Headless background monitoring (started from a shortcut/autostart)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    from credentials_file import load_credentials

    creds = load_credentials()
    if not creds:
        logger.error("Agent is not enrolled yet — run DevOpsMonitorAgent.exe first.")
        return 1

    from runtime import MonitoringLoop

    loop = MonitoringLoop(
        server_id=creds["server_id"],
        agent_token=creds["agent_token"],
        api_url=creds.get("api_url", settings.API_URL),
        interval=int(creds.get("interval_seconds", DEFAULT_INTERVAL_SECONDS)),
    )
    loop.start()
    try:
        loop.join()
    except KeyboardInterrupt:
        loop.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
