import json
from pathlib import Path

from maintainer_atlas.cli import main, report_dict, sarif
from maintainer_atlas.core import Policy, audit, diff_reports, load_snapshot


def test_healthy_fixture_passes():
    report = audit(load_snapshot("examples/healthy"))
    assert report.verdict == "pass"
    assert report.findings == ()


def test_incomplete_fixture_has_evidence_and_stable_fingerprints():
    snapshot = load_snapshot("examples/incomplete")
    first = audit(snapshot)
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
    report = audit(load_snapshot("examples/incomplete"))
    doc = sarif(report)
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"]
    assert all("ruleId" in item for item in doc["runs"][0]["results"])


def test_cli_outputs_json_and_exit_codes(tmp_path, monkeypatch):
    monkeypatch.chdir(Path(__file__).parents[1])
    output = tmp_path / "report.json"
    assert main(["audit", "examples/healthy", "--format", "json", "--output", str(output)]) == 0
    data = json.loads(output.read_text())
    assert data["verdict"] == "pass"
    assert main(["audit", "examples/incomplete", "--format", "json"]) == 2
