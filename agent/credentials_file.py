"""Secure storage for agent credentials.

After successful enrollment the agent receives a permanent agent token and
server id. This module stores those credentials safely on the local machine so
the client never has to create ``.env`` files or edit configuration by hand.

Storage location strategy:
  - Development (CLI): keep the historical ``agent_config.json`` next to the
    script so existing workflows, Docker and tests keep working unchanged.
  - Packaged (GUI/service): prefer a machine-wide location
    (``%ProgramData%\\DevOpsMonitorPro``) so the Windows service — which runs
    as LocalSystem — can read credentials enrolled by the logged-in user.
    If that location is not writable we fall back to the per-user app-data
    folder. On non-Windows platforms ``~/.config/DevOpsMonitorPro`` is used.

The file is written atomically, restricted to owner access where supported,
and is listed in the repository root ``.gitignore``. It is never committed.
"""

import json
import logging
import os
import stat
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("monitoring-agent")

APP_DIR_NAME = "DevOpsMonitorPro"
DEV_CONFIG_FILENAME = "agent_config.json"
PACKAGED_CONFIG_FILENAME = "config.json"


def _is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def _packaged_candidates() -> list:
    """Candidate config paths for the packaged agent, most-preferred first."""
    candidates = []
    # Explicit override (used by the service, tests and advanced installs).
    override = os.environ.get("DEVOPS_AGENT_CONFIG_PATH")
    if override:
        candidates.append(Path(override))
    if os.name == "nt":
        program_data = os.environ.get("ProgramData")
        if program_data:
            # Shared location: readable by the LocalSystem service account.
            candidates.append(Path(program_data) / APP_DIR_NAME / PACKAGED_CONFIG_FILENAME)
        appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        candidates.append(Path(appdata) / APP_DIR_NAME / PACKAGED_CONFIG_FILENAME)
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
        candidates.append(Path(xdg) / APP_DIR_NAME / PACKAGED_CONFIG_FILENAME)
    return candidates


def _is_writable(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        probe = path.parent / ".write_probe"
        with open(probe, "w", encoding="utf-8") as f:
            f.write("")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def get_config_path() -> Path:
    """Resolve the credential/config file path for the current run mode."""
    if _is_frozen():
        for candidate in _packaged_candidates():
            if candidate.exists() or _is_writable(candidate):
                return candidate
        return _packaged_candidates()[-1]
    return Path(__file__).resolve().parent / DEV_CONFIG_FILENAME


def _restrict_permissions(path: Path) -> None:
    """Best-effort owner-only permissions (POSIX; no-op on Windows ACLs)."""
    try:
        if os.name != "nt":
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def load_credentials() -> Optional[Dict[str, Any]]:
    """Load stored credentials, or None when the agent is not enrolled yet.

    Never raises: any corruption is logged and treated as "not enrolled".
    """
    path = get_config_path()
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data.get("server_id") or not data.get("agent_token"):
            logger.warning("Credential file %s is incomplete", path)
            return None
        return data
    except Exception as exc:  # noqa: BLE001 - corrupted file must not crash the service
        logger.warning("Failed to read credential file %s: %s", path, exc)
        return None


def save_credentials(config: Dict[str, Any]) -> Path:
    """Persist credentials atomically with restrictive permissions."""
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    _restrict_permissions(tmp_path)
    os.replace(tmp_path, path)
    logger.info("Agent credentials saved to %s", path)
    return path


def clear_credentials() -> bool:
    """Remove stored credentials (used when the agent is revoked/unenrolled)."""
    path = get_config_path()
    try:
        if path.exists():
            path.unlink()
            return True
    except OSError as exc:
        logger.warning("Failed to remove credential file %s: %s", path, exc)
    return False
