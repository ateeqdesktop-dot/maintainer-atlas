from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .core import Evidence, Finding, Policy, Report, audit, diff_reports, load_snapshot


def finding_dict(f: Finding) -> dict:
    return {**asdict(f), "evidence": [asdict(e) for e in f.evidence]}


def report_dict(r: Report) -> dict:
    return {"tool_version": r.tool_version, "snapshot_digest": r.snapshot_digest, "verdict": r.verdict, "diagnostics": list(r.diagnostics), "findings": [finding_dict(f) for f in r.findings]}


def markdown(r: Report) -> str:
    counts = {s: sum(f.severity == s for f in r.findings) for s in ("critical", "error", "warning", "info")}
    out = [f"# Maintainer Atlas report\n\n**Verdict:** `{r.verdict}`  \n**Snapshot:** `{r.snapshot_digest}`\n\n| Severity | Count |\n|---|---:|\n"]
    out += [f"| {s} | {counts[s]} |\n" for s in ("critical", "error", "warning", "info")]
    if not r.findings:
        out.append("\nNo findings. The repository passed the configured readiness policy.\n")
    for f in r.findings:
        out.append(f"\n## `{f.rule_id}` — {f.title}\n\n**Severity:** `{f.severity}`  \n{f.message}\n\n**Remediation:** {f.remediation}\n")
        if f.evidence:
            out.append("\nEvidence: " + ", ".join(f"`{e.path}`" + (f":{e.start_line}" if e.start_line else "") for e in f.evidence) + "\n")
    return "".join(out)


def sarif(r: Report) -> dict:
    results = []
    for f in r.findings:
        level = "error" if f.severity in ("error", "critical") else ("warning" if f.severity == "warning" else "note")
        results.append({"ruleId": f.rule_id, "level": level, "message": {"text": f"{f.message} Remediation: {f.remediation}"}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": e.path}, **({"region": {"startLine": e.start_line, "endLine": e.end_line}} if e.start_line else {})}} for e in f.evidence]})
    return {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json", "runs": [{"tool": {"driver": {"name": "Maintainer Atlas", "version": r.tool_version, "rules": [{"id": f.rule_id, "shortDescription": {"text": f.title}} for f in r.findings]}}, "results": results}]}


def load_policy(path: str | None) -> Policy:
    if not path:
        return Policy()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ignored = frozenset(data.get("ignore", []))
    overrides = data.get("severity", {})
    threshold = data.get("threshold", "error")
    if threshold not in ("info", "warning", "error", "critical"):
        raise ValueError("threshold must be info, warning, error, or critical")
    return Policy(ignored, overrides, threshold, data.get("waivers", {}))


def write_output(value: str, output: str | None) -> None:
    if output:
        Path(output).write_text(value, encoding="utf-8")
    else:
        print(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="maintainer-atlas", description="Evidence-backed Open Source release-readiness auditor")
    sub = parser.add_subparsers(dest="command", required=True)
    ap = sub.add_parser("audit", help="audit a local repository")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--format", choices=("json", "markdown", "sarif"), default="markdown")
    ap.add_argument("--output")
    ap.add_argument("--policy")
    ap.add_argument("--snapshot", help="write the JSON report as a baseline snapshot")
    dp = sub.add_parser("diff", help="compare two JSON reports")
    dp.add_argument("before")
    dp.add_argument("after")
    dp.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command == "diff":
            before = json.loads(Path(args.before).read_text())
            after = json.loads(Path(args.after).read_text())
            result = json.dumps({"before": before.get("snapshot_digest"), "after": after.get("snapshot_digest"), "added": sorted(set(x["fingerprint"] for x in after.get("findings", [])) - set(x["fingerprint"] for x in before.get("findings", []))), "resolved": sorted(set(x["fingerprint"] for x in before.get("findings", [])) - set(x["fingerprint"] for x in after.get("findings", [])))}, indent=2)
            write_output(result, args.output)
            return 0
        report = audit(load_snapshot(args.path), load_policy(args.policy))
        if args.snapshot:
            Path(args.snapshot).write_text(json.dumps(report_dict(report), indent=2), encoding="utf-8")
        if args.format == "json": value = json.dumps(report_dict(report), indent=2)
        elif args.format == "sarif": value = json.dumps(sarif(report), indent=2)
        else: value = markdown(report)
        write_output(value, args.output)
        return {"pass": 0, "review": 1, "block": 2}[report.verdict]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"maintainer-atlas: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
