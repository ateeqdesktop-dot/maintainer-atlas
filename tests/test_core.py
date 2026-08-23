import json
from pathlib import Path

import pytest

from maintainer_atlas.cli import main, report_dict, sarif
from maintainer_atlas.core import Policy, audit, diff_reports, load_snapshot
from maintainer_atlas.probe import execute_probes
from maintainer_atlas.probe_config import ProbeConfigError, load_probe_config


def test_healthy_fixture_passes():
    report = audit(load_snapshot("examples/healthy"))
    assert report.verdict == "pass"
    assert report.findings == ()


def test_incomplete_fixture_has_evidence_and_stable_fingerprints():
    first = audit(load_snapshot("examples/incomplete"))
    second = audit(load_snapshot("examples/incomplete"))
    assert first.verdict == "block"
    assert first.findings
    assert all(f.fingerprint and f.rule_id for f in first.findings)
    assert [f.fingerprint for f in first.findings] == [f.fingerprint for f in second.findings]


def test_ignore_and_override_policy():
    report = audit(load_snapshot("examples/incomplete"), Policy(frozenset({"license.present"}), {"ci.workflow_present": "warning"}, "critical"))
    assert all(f.rule_id != "license.present" for f in report.findings)
    assert any(f.rule_id == "ci.workflow_present" and f.severity == "warning" for f in report.findings)
    assert report.verdict == "review"


def test_diff_reports_new_and_resolved():
    old = audit(load_snapshot("examples/incomplete"))
    new = audit(load_snapshot("examples/healthy"))
    result = diff_reports(old, new)
    assert result["resolved"]
    assert result["added"] == []


def test_sarif_shape():
    doc = sarif(audit(load_snapshot("examples/incomplete")))
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"]
    assert all("ruleId" in item for item in doc["runs"][0]["results"])


def test_cli_outputs_json_and_exit_codes(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parents[1])
    output = tmp_path / "report.json"
    assert main(["audit", "examples/healthy", "--format", "json", "--output", str(output)]) == 0
    assert json.loads(output.read_text())["verdict"] == "pass"
    assert main(["audit", "examples/incomplete", "--format", "json"]) == 2


def write_probe_config(path: Path, command: list[str], *, optional: bool = False, timeout: int | None = None) -> None:
    timeout_line = f"timeout_seconds = {timeout}\n" if timeout else ""
    path.write_text(
        "version = 1\nprofile = 'test'\ntimeout_seconds = 5\nmax_output_bytes = 32\nnetwork = 'deny'\n\n"
        "[[steps]]\nid = 'step'\n"
        + f"command = {json.dumps(command)}\n"
        + f"optional = {'true' if optional else 'false'}\n"
        + timeout_line,
        encoding="utf-8",
    )


def test_probe_pass_and_digest_are_stable(tmp_path):
    config_path = tmp_path / "probe.toml"
    write_probe_config(config_path, ["python", "-c", "print('ok')"])
    config = load_probe_config(config_path)
    first = execute_probes(tmp_path, config)
    second = execute_probes(tmp_path, config)
    assert first.verdict == "pass"
    assert first.steps[0].status == "passed"
    assert first.evidence_digest == second.evidence_digest
    assert first.steps[0].stdout_digest == second.steps[0].stdout_digest


def test_probe_dry_run_does_not_execute(tmp_path):
    config_path = tmp_path / "probe.toml"
    write_probe_config(config_path, ["python", "-c", "raise SystemExit(9)"])
    result = execute_probes(tmp_path, load_probe_config(config_path), dry_run=True)
    assert result.verdict == "planned"
    assert result.steps[0].status == "planned"


def test_optional_probe_failure_is_review(tmp_path):
    config_path = tmp_path / "probe.toml"
    write_probe_config(config_path, ["python", "-c", "raise SystemExit(3)"], optional=True)
    result = execute_probes(tmp_path, load_probe_config(config_path))
    assert result.verdict == "review"
    assert result.steps[0].status == "failed"


def test_probe_timeout_is_blocking(tmp_path):
    config_path = tmp_path / "probe.toml"
    write_probe_config(config_path, ["python", "-c", "import time; time.sleep(1)"], timeout=1)
    result = execute_probes(tmp_path, load_probe_config(config_path))
    assert result.steps[0].status == "timeout"
    assert result.verdict == "block"


def test_probe_config_rejects_duplicate_ids_and_empty_commands(tmp_path):
    config = tmp_path / "bad.toml"
    config.write_text("version=1\n[[steps]]\nid='x'\ncommand=[]\n", encoding="utf-8")
    with pytest.raises(ProbeConfigError):
        load_probe_config(config)


def test_probe_cli_json(tmp_path):
    config = tmp_path / ".atlas-probe.toml"
    write_probe_config(config, ["python", "-c", "print('cli')"])
    output = tmp_path / "evidence.json"
    assert main(["probe", str(tmp_path), "--config", str(config), "--format", "json", "--output", str(output)]) == 0
    data = json.loads(output.read_text())
    assert data["verdict"] == "pass"
    assert data["evidence_digest"]
