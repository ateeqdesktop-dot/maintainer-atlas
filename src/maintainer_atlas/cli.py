from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from xml.sax.saxutils import escape

from .core import Finding, Policy, Report, audit, load_snapshot
from .evidence import classify_against_baseline, evidence_id, finding_dict, junit, report_dict
from .probe import ProbeReport, execute_probes
from .probe_config import ProbeConfigError, load_probe_config


def probe_dict(report: ProbeReport) -> dict:
    return {**asdict(report), "schema_version": 1, "steps": [asdict(step) for step in report.steps]}


def markdown(report: Report, baseline: dict | None = None) -> str:
    bundle = classify_against_baseline(report, baseline)
    counts = {severity: sum(item["severity"] == severity and item["status"] != "resolved" for item in bundle["findings"]) for severity in ("critical", "error", "warning", "info")}
    summary = bundle["summary"]
    out = [f"# Maintainer Atlas report\n\n**Verdict:** `{report.verdict}`  \n**Evidence ID:** `{bundle['evidence_id']}`  \n**Snapshot:** `{report.snapshot_digest}`\n\n", f"| Severity | Count |\n|---|---:|\n"]
    out += [f"| {severity} | {counts[severity]} |\n" for severity in ("critical", "error", "warning", "info")]
    out.append(f"\nBaseline: **{summary['new']} new**, **{summary['unchanged']} unchanged**, **{summary['resolved']} resolved**.\n")
    active = [item for item in bundle["findings"] if item["status"] != "resolved"]
    if not active:
        out.append("\nNo active findings. The repository passed the configured readiness policy.\n")
    for item in bundle["findings"]:
        if item["status"] == "resolved":
            continue
        out.append(f"\n## `{item['rule_id']}` — {item['title']}\n\n**Severity:** `{item['severity']}`  \n**Status:** `{item['status']}`  \n{item['message']}\n\n**Remediation:** {item['remediation']}\n")
        if item["evidence"]:
            out.append("\nEvidence: " + ", ".join(f"`{entry['path']}`" + (f":{entry['start_line']}" if entry.get("start_line") else "") for entry in item["evidence"]) + "\n")
    return "".join(out)


def probe_markdown(report: ProbeReport) -> str:
    out = ["# Atlas Probe evidence\n\n", f"**Verdict:** `{report.verdict}`  \n**Evidence digest:** `{report.evidence_digest}`  \n", f"**Config digest:** `{report.config_digest}`  \n**Network policy:** `{report.network_policy}`\n\n", "| Step | Status | Exit | Duration (ms) | stdout bytes | stderr bytes |\n|---|---|---:|---:|---:|---:|\n"]
    for step in report.steps:
        out.append(f"| `{step.id}` | `{step.status}` | {step.exit_code if step.exit_code is not None else '—'} | {step.duration_ms} | {step.stdout_bytes} | {step.stderr_bytes} |\n")
    if report.diagnostics:
        out.append("\n## Diagnostics\n\n" + "\n".join(f"- {item}" for item in report.diagnostics) + "\n")
    out.append("\nRaw output is excluded by default; only digests and bounded sizes are recorded.\n")
    return "".join(out)


def sarif(report: Report) -> dict:
    results = []
    for item in report.findings:
        level = "error" if item.severity in ("error", "critical") else ("warning" if item.severity == "warning" else "note")
        results.append({"ruleId": item.rule_id, "level": level, "message": {"text": f"{item.message} Remediation: {item.remediation}"}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": evidence.path}, **({"region": {"startLine": evidence.start_line, "endLine": evidence.end_line}} if evidence.start_line else {})}} for evidence in item.evidence]})
    return {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json", "runs": [{"tool": {"driver": {"name": "Maintainer Atlas", "version": report.tool_version, "rules": [{"id": item.rule_id, "shortDescription": {"text": item.title}} for item in report.findings]}}, "results": results}]}


def load_policy(path: str | None) -> Policy:
    if not path:
        return Policy()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    threshold = data.get("threshold", "error")
    if threshold not in ("info", "warning", "error", "critical"):
        raise ValueError("threshold must be info, warning, error, or critical")
    return Policy(frozenset(data.get("ignore", [])), data.get("severity", {}), threshold, data.get("waivers", {}))


def write_output(value: str, output: str | None) -> None:
    if output:
        Path(output).write_text(value, encoding="utf-8")
    else:
        print(value)


def read_baseline(path: str | None) -> dict | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="maintainer-atlas", description="Evidence-backed Open Source release readiness auditor")
    sub = parser.add_subparsers(dest="command", required=True)
    audit_parser = sub.add_parser("audit", help="audit a local repository without executing repository code")
    audit_parser.add_argument("path", nargs="?", default=".")
    audit_parser.add_argument("--format", choices=("json", "markdown", "sarif", "junit"), default="markdown")
    audit_parser.add_argument("--output")
    audit_parser.add_argument("--policy")
    audit_parser.add_argument("--snapshot", help="write a JSON evidence baseline")
    audit_parser.add_argument("--baseline", help="compare findings against a prior JSON report")
    probe_parser = sub.add_parser("probe", help="run an explicit, bounded contributor-readiness probe plan")
    probe_parser.add_argument("path", nargs="?", default=".")
    probe_parser.add_argument("--config", default=".atlas-probe.toml")
    probe_parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    probe_parser.add_argument("--output")
    probe_parser.add_argument("--dry-run", action="store_true")
    probe_parser.add_argument("--include-output", action="store_true")
    diff_parser = sub.add_parser("diff", help="compare two JSON reports")
    diff_parser.add_argument("before")
    diff_parser.add_argument("after")
    diff_parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command == "diff":
            before = json.loads(Path(args.before).read_text())
            after = json.loads(Path(args.after).read_text())
            before_keys = {item["fingerprint"] for item in before.get("findings", [])}
            after_keys = {item["fingerprint"] for item in after.get("findings", [])}
            write_output(json.dumps({"before": before.get("snapshot_digest"), "after": after.get("snapshot_digest"), "added": sorted(after_keys - before_keys), "resolved": sorted(before_keys - after_keys)}, indent=2), args.output)
            return 0
        if args.command == "probe":
            config_path = Path(args.path, args.config) if not Path(args.config).is_absolute() else Path(args.config)
            result = execute_probes(args.path, load_probe_config(config_path), dry_run=args.dry_run, include_output=args.include_output)
            write_output(json.dumps(probe_dict(result), indent=2) if args.format == "json" else probe_markdown(result), args.output)
            return {"planned": 0, "pass": 0, "review": 1, "block": 2}[result.verdict]
        report = audit(load_snapshot(args.path), load_policy(args.policy))
        baseline = read_baseline(args.baseline)
        bundle = classify_against_baseline(report, baseline)
        if args.snapshot:
            Path(args.snapshot).write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
        if args.format == "json":
            value = json.dumps(bundle, indent=2, ensure_ascii=False)
        elif args.format == "sarif":
            value = json.dumps(sarif(report), indent=2)
        elif args.format == "junit":
            value = junit(report, baseline)
        else:
            value = markdown(report, baseline)
        write_output(value, args.output)
        return {"pass": 0, "review": 1, "block": 2}[report.verdict]
    except (OSError, ValueError, ProbeConfigError, json.JSONDecodeError) as exc:
        print(f"maintainer-atlas: {escape(str(exc))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
