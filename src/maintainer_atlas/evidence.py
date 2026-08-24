"""Canonical evidence bundles and baseline comparison for Maintainer Atlas."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from .core import Finding, Report


def finding_dict(finding: Finding) -> dict[str, Any]:
    return {**asdict(finding), "evidence": [asdict(item) for item in finding.evidence]}


def report_dict(report: Report) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "tool_version": report.tool_version,
        "snapshot_digest": report.snapshot_digest,
        "verdict": report.verdict,
        "diagnostics": list(report.diagnostics),
        "findings": [finding_dict(item) for item in report.findings],
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def evidence_id(report: Report) -> str:
    payload = report_dict(report)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def classify_against_baseline(report: Report, baseline: dict[str, Any] | None) -> dict[str, Any]:
    current = {item["fingerprint"]: item for item in report_dict(report)["findings"]}
    previous = {item["fingerprint"]: item for item in (baseline or {}).get("findings", [])}
    for item in current.values():
        item["status"] = "unchanged" if item["fingerprint"] in previous else "new"
    resolved = [dict(item, status="resolved") for key, item in previous.items() if key not in current]
    return {
        "schema_version": 1,
        "evidence_id": evidence_id(report),
        "snapshot_digest": report.snapshot_digest,
        "verdict": report.verdict,
        "diagnostics": list(report.diagnostics),
        "findings": sorted([*current.values(), *resolved], key=lambda x: (x["status"], x["rule_id"], x["fingerprint"])),
        "summary": {"new": sum(x["status"] == "new" for x in current.values()), "unchanged": sum(x["status"] == "unchanged" for x in current.values()), "resolved": len(resolved)},
    }


def junit(report: Report, baseline: dict[str, Any] | None = None) -> str:
    bundle = classify_against_baseline(report, baseline)
    cases = []
    for item in bundle["findings"]:
        if item["status"] == "resolved":
            continue
        case = f'<testcase classname="maintainer-atlas.{item["category"]}" name="{item["rule_id"]}">'
        if item["severity"] in ("critical", "error"):
            case += f'<failure message="{item["title"]}">{item["message"]} Remediation: {item["remediation"]}</failure>'
        elif item["severity"] == "warning":
            case += f'<system-out>{item["message"]}</system-out>'
        case += "</testcase>"
        cases.append(case)
    return f'<testsuite name="Maintainer Atlas" tests="{len(cases)}" failures="{sum(item["severity"] in ("critical", "error") for item in bundle["findings"] if item["status"] != "resolved")}">' + "".join(cases) + "</testsuite>\n"
