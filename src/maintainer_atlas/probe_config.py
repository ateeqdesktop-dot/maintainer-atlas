from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import hashlib
import json

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    tomllib = None


class ProbeConfigError(ValueError):
    """Raised when a probe configuration is invalid or unsafe."""


@dataclass(frozen=True)
class ProbeStep:
    id: str
    command: tuple[str, ...]
    optional: bool = False
    timeout_seconds: int | None = None


@dataclass(frozen=True)
class ProbeConfig:
    version: int
    profile: str
    timeout_seconds: int
    max_output_bytes: int
    network: str
    steps: tuple[ProbeStep, ...]

    def canonical(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "profile": self.profile,
            "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
            "network": self.network,
            "steps": [
                {
                    "id": step.id,
                    "command": list(step.command),
                    "optional": step.optional,
                    "timeout_seconds": step.timeout_seconds,
                }
                for step in self.steps
            ],
        }

    @property
    def digest(self) -> str:
        payload = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(payload).hexdigest()


def _load_toml(path: Path) -> dict[str, Any]:
    if tomllib is None:
        try:
            import tomli
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise ProbeConfigError("Python 3.10 requires the 'tomli' dependency") from exc
        loader = tomli.loads
    else:
        loader = tomllib.loads
    try:
        return loader(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ProbeConfigError(str(exc)) from exc
    except Exception as exc:
        raise ProbeConfigError(f"invalid TOML: {exc}") from exc


def _positive_int(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
        raise ProbeConfigError(f"{name} must be an integer from 1 to {maximum}")
    return value


def load_probe_config(path: str | Path) -> ProbeConfig:
    config_path = Path(path)
    data = _load_toml(config_path)
    version = data.get("version", 1)
    if version != 1:
        raise ProbeConfigError("only probe configuration version 1 is supported")
    profile = data.get("profile", "custom")
    if not isinstance(profile, str) or not profile or len(profile) > 64:
        raise ProbeConfigError("profile must be a non-empty string of at most 64 characters")
    timeout = _positive_int(data.get("timeout_seconds", 120), "timeout_seconds", 3600)
    max_output = _positive_int(data.get("max_output_bytes", 65536), "max_output_bytes", 4_000_000)
    network = data.get("network", "deny")
    if network not in {"deny", "allow"}:
        raise ProbeConfigError("network must be 'deny' or 'allow'")
    raw_steps = data.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps or len(raw_steps) > 32:
        raise ProbeConfigError("steps must contain between 1 and 32 entries")
    steps: list[ProbeStep] = []
    ids: set[str] = set()
    for index, raw in enumerate(raw_steps, 1):
        if not isinstance(raw, dict):
            raise ProbeConfigError(f"steps[{index}] must be a table")
        step_id = raw.get("id")
        command = raw.get("command")
        if not isinstance(step_id, str) or not step_id or step_id in ids or len(step_id) > 80:
            raise ProbeConfigError(f"steps[{index}].id must be unique and non-empty")
        if not isinstance(command, list) or not command or len(command) > 32 or not all(isinstance(x, str) and x and "\x00" not in x for x in command):
            raise ProbeConfigError(f"steps[{index}].command must be a non-empty string array without NUL bytes")
        optional = raw.get("optional", False)
        if not isinstance(optional, bool):
            raise ProbeConfigError(f"steps[{index}].optional must be boolean")
        step_timeout = raw.get("timeout_seconds")
        if step_timeout is not None:
            step_timeout = _positive_int(step_timeout, f"steps[{index}].timeout_seconds", timeout)
        ids.add(step_id)
        steps.append(ProbeStep(step_id, tuple(command), optional, step_timeout))
    return ProbeConfig(1, profile, timeout, max_output, network, tuple(steps))
