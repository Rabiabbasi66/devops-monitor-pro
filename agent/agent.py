"""DevOps Monitor Pro agent — command-line entrypoint.

Development / server mode (unchanged behaviour):

    python agent.py                # run monitoring with existing config/env
    python agent.py --enroll "TOKEN"

Client mode (packaged Windows agent):

    DevOpsMonitorAgent.exe --enroll "TOKEN"     # enroll, confirm, start GUI
    DevOpsMonitorAgent.exe --tray               # start monitoring silently
    DevOpsMonitorAgent.exe                      # opens the enrollment GUI window

Installer mode (used by DevOpsMonitorAgent-Setup.exe; never prints secrets):

    DevOpsMonitorAgent.exe --enroll-only "TOKEN"               # enroll, exit
    DevOpsMonitorAgent.exe --enroll-only "TOKEN" --result-file PATH
    DevOpsMonitorAgent.exe --token-file C:/path/token.txt      # token from file

Installer contract: ``--enroll-only`` exits 0 on success and 1 on failure. If
``--result-file`` is given, a plain-text result ("OK" or a human-readable error
message, never a token) is written there so the installer can show it.

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
    EnrollmentError,
    collect_all,
    enroll_agent,
    send_metrics,
)

logger = logging.getLogger("monitoring-agent")

APP_TITLE = "DevOps Monitor Pro Agent"


# ---------------------------------------------------------------------------
# Mode detection & logging helpers
# ---------------------------------------------------------------------------


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _is_windows() -> bool:
    return os.name == "nt"


def _setup_logging() -> None:
    """Configure logging (no-op sink when stdout/stderr are unavailable)."""
    if sys.stdout is None or sys.stderr is None:
        # Windowed (GUI) frozen build: no console attached.
        logging.basicConfig(level=logging.INFO, handlers=[logging.NullHandler()])
    else:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
        )


def _show_message(kind: str, message: str) -> None:
    """Best-effort message box (used by the windowed build for CLI feedback)."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        if kind == "error":
            messagebox.showerror(APP_TITLE, message)
        else:
            messagebox.showinfo(APP_TITLE, message)
        root.destroy()
    except Exception:  # noqa: BLE001 - feedback must never crash the agent
        pass


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
# Installer contract: enroll, report result, exit (no monitoring loop here)
# ---------------------------------------------------------------------------


def _read_token_file(path: str) -> str:
    """Read a one-time enrollment token from a UTF-8 text file."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read().strip()
    except OSError:
        return ""


def _write_result_file(path: str, message: str) -> None:
    """Best-effort machine-readable result for the installer (no secrets)."""
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(message)
    except OSError:
        pass


def _enroll_only(args) -> int:
    """Enroll and exit - the contract the Setup installer relies on.

    Exits 0 on success, 1 on failure. Prints ``AGENT-ENROLL-OK`` /
    ``AGENT-ENROLL-FAIL: <reason>`` when a console is attached, and optionally
    writes a plain-text result via ``--result-file``. The permanent agent token
    is never printed or written.
    """
    _setup_logging()

    token = args.enroll_only if args.enroll_only is not None else ""
    if args.token_file is not None:
        token = _read_token_file(args.token_file)
    token = (token or "").strip().strip('"').strip("'")
    if not token:
        message = "No enrollment token was provided."
        print(f"AGENT-ENROLL-FAIL: {message}")
        _write_result_file(args.result_file, message)
        return 1

    try:
        enroll_agent(token)
    except EnrollmentError as exc:
        print(f"AGENT-ENROLL-FAIL: {exc.message}")
        _write_result_file(args.result_file, exc.message)
        return 1
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected enrollment error")
        message = "Unexpected error during enrollment. Please try again."
        print(f"AGENT-ENROLL-FAIL: {message}")
        _write_result_file(args.result_file, message)
        return 1

    print("AGENT-ENROLL-OK")
    _write_result_file(args.result_file, "OK")
    return 0


def _frozen_windows_enroll(enrollment_code: str) -> int:
    """Enroll from the CLI in the windowed (GUI) build.

    The packaged exe has no console, so feedback is given with message boxes,
    then the agent GUI opens and starts monitoring automatically.
    """
    _setup_logging()
    if not (enrollment_code or "").strip().strip('"').strip("'"):
        _show_message(
            "error",
            "No enrollment token was provided.\n\n"
            "Paste the one-time code from your dashboard "
            "(Servers → Install Agent → Generate Enrollment Code).",
        )
        import gui

        return gui.main()
    try:
        enroll_agent(enrollment_code)
    except EnrollmentError as exc:
        _show_message("error", exc.message)
        return 1
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected enrollment error")
        _show_message("error", "Unexpected error during enrollment. Please try again.")
        return 1

    _show_message(
        "info",
        "Agent enrolled successfully.\n\nThe agent window will open now and "
        "start monitoring automatically.",
    )
    import gui

    return gui.main()


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
    _setup_logging()

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
    parser.add_argument(
        "--enroll-only",
        metavar="TOKEN",
        help="Enroll with TOKEN, then exit (used by the Setup installer; "
        "monitoring is started separately)",
    )
    parser.add_argument(
        "--token-file",
        metavar="PATH",
        help="Read the enrollment token from PATH and behave like --enroll-only",
    )
    parser.add_argument(
        "--result-file",
        metavar="PATH",
        help="Write a plain-text enrollment result (OK or error message; "
        "never a token) to PATH",
    )
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

    # Installer contract: enroll, report machine-readable success, exit.
    # Presence checks (not truthiness) so empty strings are still handled here.
    if args.enroll_only is not None or args.token_file is not None:
        return _enroll_only(args)

    # Windowed build + --enroll: message-box feedback, then open the GUI.
    if args.enroll is not None and _is_frozen() and _is_windows():
        return _frozen_windows_enroll(args.enroll)

    mode = _resolve_runtime_mode(args)

    if mode == "gui":
        import gui

        return gui.main()

    if mode == "tray":
        return _run_tray()

    return run_console_mode(args)


def _run_tray() -> int:
    """Headless background monitoring (started from a shortcut/autostart)."""
    _setup_logging()
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
