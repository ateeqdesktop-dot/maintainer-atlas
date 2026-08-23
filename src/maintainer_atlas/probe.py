from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import os
import subprocess
import time
from typing import Any

from .probe_config import ProbeConfig, ProbeStep


@dataclass(frozen=True)
class ProbeStepResult:
    id: str
    command: tuple[str, ...]
    status: str
    exit_code: int | None
    duration_ms: int
    stdout_bytes: int
    stderr_bytes: int
    stdout_digest: str
    stderr_digest: str
    stdout_preview: str = ""
    stderr_preview: str = ""
    optional: bool = False

    def stable_payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("duration_ms", None)
        value.pop("stdout_preview", None)
        value.pop("stderr_preview", None)
        return value


@dataclass(frozen=True)
class ProbeReport:
    tool_version: str
    config_digest: str
    repository: str
    network_policy: str
    verdict: str
    steps: tuple[ProbeStepResult, ...]
    diagnostics: tuple[str, ...] = ()
    evidence_digest: str = ""

    def with_digest(self) -> "ProbeReport":
        payload = {
            "tool_version": self.tool_version,
            "config_digest": self.config_digest,
            "network_policy": self.network_policy,
            "verdict": self.verdict,
            "steps": [step.stable_payload() for step in self.steps],
            "diagnostics": list(self.diagnostics),
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return ProbeReport(**{**asdict(self), "evidence_digest": digest, "steps": self.steps})


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bounded(data: bytes, limit: int) -> tuple[bytes, bool]:
    if len(data) <= limit:
        return data, False
    return data[:limit], True


def _result_for_spawn_error(step: ProbeStep, message: str) -> ProbeStepResult:
    raw = message.encode("utf-8", "replace")
    return ProbeStepResult(step.id, step.command, "spawn_error", None, 0, 0, len(raw), _digest(b""), _digest(raw), "", message[:512], step.optional)


def execute_probes(root: str | os.PathLike[str], config: ProbeConfig, *, dry_run: bool = False, include_output: bool = False) -> ProbeReport:
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise ValueError(f"repository path is not a directory: {root}")
    if dry_run:
        steps = tuple(ProbeStepResult(step.id, step.command, "planned", None, 0, 0, 0, _digest(b""), _digest(b""), optional=step.optional) for step in config.steps)
        return ProbeReport("0.2.0", config.digest, str(base), config.network, "planned", steps).with_digest()

    results: list[ProbeStepResult] = []
    diagnostics: list[str] = []
    for step in config.steps:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                list(step.command),
                cwd=base,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=step.timeout_seconds or config.timeout_seconds,
                check=False,
                env={"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")},
            )
            stdout, stdout_truncated = _bounded(completed.stdout, config.max_output_bytes)
            stderr, stderr_truncated = _bounded(completed.stderr, config.max_output_bytes)
            status = "passed" if completed.returncode == 0 else "failed"
            if stdout_truncated or stderr_truncated:
                diagnostics.append(f"output truncated for step {step.id}")
            results.append(ProbeStepResult(
                step.id, step.command, status, completed.returncode,
                int((time.monotonic() - started) * 1000), len(completed.stdout), len(completed.stderr),
                _digest(completed.stdout), _digest(completed.stderr),
                stdout.decode("utf-8", "replace")[:512] if include_output else "",
                stderr.decode("utf-8", "replace")[:512] if include_output else "",
                step.optional,
            ))
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            if isinstance(stdout, str): stdout = stdout.encode()
            if isinstance(stderr, str): stderr = stderr.encode()
            results.append(ProbeStepResult(
                step.id, step.command, "timeout", None, int((time.monotonic() - started) * 1000),
                len(stdout), len(stderr), _digest(stdout), _digest(stderr), optional=step.optional,
            ))
        except (OSError, ValueError) as exc:
            results.append(_result_for_spawn_error(step, str(exc)))

    blocking = any(step.status not in {"passed"} and not step.optional for step in results)
    review = any(step.status not in {"passed"} and step.optional for step in results)
    verdict = "block" if blocking else ("review" if review else "pass")
    return ProbeReport("0.2.0", config.digest, str(base), config.network, verdict, tuple(results), tuple(diagnostics)).with_digest()
