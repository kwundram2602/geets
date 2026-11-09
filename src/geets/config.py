"""Per-device Earth Engine settings in a .env file, plus authentication helpers.

The file defaults to ``~/.config/geets/.env`` (override with ``GEETS_ENV_FILE``) so that
scripts, notebooks and the QGIS plugin all share one place, outside every repository.

Keys:
    EE_PROJECT   Google Cloud project with the Earth Engine API enabled.
"""

from __future__ import annotations

import os
from pathlib import Path

import ee

ENV_VAR = "GEETS_ENV_FILE"
CONFIG_KEYS = {"EE_PROJECT": "Google Cloud project with the Earth Engine API enabled"}
EE_CREDENTIALS = Path.home() / ".config" / "earthengine" / "credentials"


def config_path() -> Path:
    """Path of the geets .env file: ``GEETS_ENV_FILE`` or ``~/.config/geets/.env``."""
    override = os.environ.get(ENV_VAR)
    return (
        Path(override).expanduser() if override else Path.home() / ".config/geets/.env"
    )


def _parse(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def load_config() -> dict[str, str]:
    """All keys of the .env file; known keys that are missing are returned as ""."""
    path = config_path()
    values = _parse(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return {key: values.get(key, "") for key in CONFIG_KEYS} | values


def save_config(values: dict[str, str]) -> str:
    """Merge ``values`` into the .env file (empty value removes the key).

    Unknown keys and comments already in the file are kept. The file is created with
    mode 600 because it may hold project ids the user does not want to share.
    Returns the file path.
    """
    path = config_path()
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    pending = {k: str(v).strip() for k, v in values.items()}
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip().removeprefix("export ").strip()
        if "=" in line and not line.lstrip().startswith("#") and key in pending:
            value = pending.pop(key)
            if value:
                out.append(f"{key}={value}")
            continue
        out.append(line)
    out += [f"{key}={value}" for key, value in pending.items() if value]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return str(path)


def _project(project: str | None) -> str:
    project = (
        project or load_config().get("EE_PROJECT") or os.environ.get("EE_PROJECT", "")
    )
    if not project:
        raise ValueError(
            "No Earth Engine project set. "
            f"Add EE_PROJECT=<cloud project id> to {config_path()}"
        )
    return project


def init_from_config(project: str | None = None) -> str:
    """Initialize Earth Engine with the .env project; returns the project id."""
    project = _project(project)
    ee.Initialize(project=project)
    return project


def authenticate_from_config(force: bool = False) -> dict:
    """Browser login (Google OAuth via localhost redirect), then initialize and test.

    Opens the system browser; the token is stored by earthengine-api in
    ``~/.config/earthengine/credentials``. ``force`` re-runs the login even if a
    token exists.
    """
    ee.Authenticate(auth_mode="localhost", force=force)
    return ee_status()


def ee_status() -> dict:
    """Check config, stored credentials and a real round trip to Earth Engine."""
    status = {
        "config_path": str(config_path()),
        "project": load_config().get("EE_PROJECT", ""),
        "credentials": EE_CREDENTIALS.is_file(),
        "ok": False,
        "message": "",
    }
    if not status["credentials"]:
        status["message"] = "Not authenticated: run the browser login first."
        return status
    try:
        init_from_config()
        ee.Number(1).getInfo()
    except Exception as exc:  # noqa: BLE001 - reported to the caller as text
        status["message"] = str(exc)
        return status
    status["ok"] = True
    status["message"] = f"Connected to Earth Engine (project {status['project']})."
    return status


def ensure_initialized() -> None:
    """Initialize from the .env file unless Earth Engine is already initialized."""
    if not ee.data.is_initialized():
        init_from_config()
