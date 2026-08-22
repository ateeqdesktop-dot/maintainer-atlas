from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable, Iterable

SEVERITIES = ("info", "warning", "error", "critical")
SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITIES)}
MAX_FILES = 5000
MAX_FILE_BYTES = 256_000
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build"}

@dataclass(frozen=True)
class Evidence:
    path: str
    start_line: int | None = None
    end_line: int | None = None

@dataclass(frozen=True)
class Finding:
    rule_id: str
    title: str
    category: str
    severity: str
    message: str
    remediation: str
    evidence: tuple[Evidence, ...] = ()
    fingerprint: str = ""

    def with_fingerprint(self) -> "Finding":
        raw = json.dumps({"rule_id": self.rule_id, "message": self.message, "evidence": [asdict(e) for e in self.evidence]}, sort_keys=True)
        return Finding(**{**asdict(self), "fingerprint": hashlib.sha256(raw.encode()).hexdigest()[:20], "evidence": self.evidence})

@dataclass(frozen=True)
class RepositorySnapshot:
    root: str
    files: tuple[str, ...]
    ecosystems: tuple[str, ...]
    file_sizes: dict[str, int]
    digest: str

@dataclass(frozen=True)
class Policy:
    ignored_rules: frozenset[str] = frozenset()
    severity_overrides: dict[str, str] = field(default_factory=dict)
    threshold: str = "error"
    waivers: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class Report:
    tool_version: str
    snapshot_digest: str
    verdict: str
    findings: tuple[Finding, ...]
    diagnostics: tuple[str, ...] = ()


def _safe_rel(root: Path, path: Path) -> str | None:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return None


def load_snapshot(root: str | os.PathLike[str]) -> RepositorySnapshot:
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        raise ValueError(f"repository path is not a directory: {root}")
    records: list[tuple[str, int]] = []
    for current, dirs, names in os.walk(base, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not Path(current, d).is_symlink())
        for name in sorted(names):
            path = Path(current, name)
            rel = _safe_rel(base, path)
            if rel is None or path.is_symlink() or len(records) >= MAX_FILES:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            records.append((rel, size))
    records.sort()
    files = tuple(p for p, _ in records)
    sizes = dict(records)
    ecosystems = set()
    if any(p.endswith(".py") or p in {"pyproject.toml", "setup.py"} for p in files): ecosystems.add("python")
    if any(p.endswith((".ts", ".tsx", ".js", ".jsx")) or p in {"package.json", "package-lock.json", "pnpm-lock.yaml"} for p in files): ecosystems.add("javascript")
    if any(p.endswith(".rs") or p == "Cargo.toml" for p in files): ecosystems.add("rust")
    if any(p.endswith((".go",)) or p == "go.mod" for p in files): ecosystems.add("go")
    digest = hashlib.sha256(json.dumps({"files": records, "ecosystems": sorted(ecosystems)}, sort_keys=True).encode()).hexdigest()
    return RepositorySnapshot(str(base), files, tuple(sorted(ecosystems)), sizes, digest)


def read_text(snapshot: RepositorySnapshot, rel: str) -> str:
    if rel not in snapshot.files or snapshot.file_sizes.get(rel, 0) > MAX_FILE_BYTES:
        return ""
    path = Path(snapshot.root, rel).resolve()
    try:
        if path.is_symlink() or not path.is_file() or Path(snapshot.root) not in path.parents:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def evidence(path: str, text: str = "") -> tuple[Evidence, ...]:
    line = next((i for i, value in enumerate(text.splitlines(), 1) if value.strip()), None)
    return (Evidence(path, line, line),) if line else (Evidence(path),)


def finding(rule_id: str, title: str, category: str, severity: str, message: str, remediation: str, ev: Iterable[Evidence] = ()) -> Finding:
    return Finding(rule_id, title, category, severity, message, remediation, tuple(ev)).with_fingerprint()

Rule = Callable[[RepositorySnapshot], Iterable[Finding]]


def _presence(rule_id: str, title: str, category: str, candidates: tuple[str, ...], remediation: str, severity: str = "error") -> Rule:
    def check(snapshot: RepositorySnapshot):
        hit = next((p for p in candidates if p in snapshot.files), None)
        if not hit:
            yield finding(rule_id, title, category, severity, f"None of the expected files were found: {', '.join(candidates)}.", remediation)
    return check


def rule_license(s):
    if not any(p == "LICENSE" or p.startswith("LICENSE.") or p == "COPYING" or p.startswith("COPYING.") for p in s.files):
        yield finding("license.present", "License is discoverable", "governance", "critical", "No root-level LICENSE or COPYING file was found.", "Add a standard OSI-approved license and link it from the README.")

def rule_readme(s):
    if not any(p.lower() in {"readme", "readme.md", "readme.rst", "readme.txt"} for p in s.files):
        yield finding("docs.readme_present", "README is present", "documentation", "error", "No README file was found at the repository root.", "Add a README with purpose, installation, a minimal example, and support boundaries.")
    else:
        text = next((read_text(s, p) for p in s.files if p.lower() in {"readme", "readme.md", "readme.rst", "readme.txt"}), "")
        if not any(word in text.lower() for word in ("install", "quick start", "usage", "getting started")):
            yield finding("docs.quickstart_present", "README has a quickstart", "documentation", "warning", "README does not contain recognizable installation or usage guidance.", "Add a copy-paste quickstart for a clean checkout.", evidence("README"))

def rule_contributing(s):
    if not any(p.lower() in {"contributing.md", "docs/contributing.md"} for p in s.files):
        yield finding("community.contributing_present", "Contribution guide is present", "community", "warning", "No CONTRIBUTING guide was found.", "Document local setup, quality gates, commit expectations, and how to propose changes.")

def rule_security(s):
    if not any(p.lower() in {"security.md", ".github/security.md"} for p in s.files):
        yield finding("security.policy_present", "Security policy is present", "security", "warning", "No SECURITY.md was found.", "Add private vulnerability-reporting instructions and supported-version policy.")

def rule_community(s):
    checks = [("community.code_of_conduct", ("CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md"), "Add a Code of Conduct."), ("community.issue_templates", (".github/ISSUE_TEMPLATE",), "Add issue templates for reproducible bug reports and feature proposals."), ("community.pull_request_template", (".github/PULL_REQUEST_TEMPLATE.md",), "Add a pull request template with testing and documentation prompts."), ("ownership.codeowners_present", (".github/CODEOWNERS", "CODEOWNERS"), "Add CODEOWNERS so review ownership is explicit.")]
    for rid, candidates, fix in checks:
        if not any(p in s.files or any(x.startswith(p.rstrip("/") + "/") for x in s.files) for p in candidates):
            yield finding(rid, rid.replace(".", " ").title(), "community", "warning", f"No artifact matching {candidates[0]} was found.", fix)

def rule_ci(s):
    workflows = [p for p in s.files if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))]
    if not workflows:
        yield finding("ci.workflow_present", "Continuous integration is present", "delivery", "error", "No GitHub Actions workflow was found.", "Add CI that runs tests and static checks on pull requests.")
    for p in workflows:
        text = read_text(s, p)
        if any(re.search(r"^\s*-\s*uses:\s*[^@\s]+@v\d", line) for line in text.splitlines()):
            yield finding("ci.workflow_pinned_actions", "Workflow actions are pinned", "delivery", "warning", f"Workflow {p} appears to use mutable action tags.", "Pin third-party actions to immutable commit SHAs and document the update process.", evidence(p, text))

def rule_tests(s):
    names = ("tests", "test", "spec", "__tests__")
    if not any(any(part == n for part in p.split("/")) for p in s.files for n in names) and not any((Path(p).name.startswith("test_") and p.endswith(".py")) or p.endswith(("_test.py", ".test.ts", ".spec.ts", "_test.go")) for p in s.files):
        yield finding("tests.detected", "Automated tests are discoverable", "quality", "error", "No conventional test directory or test-named file was detected.", "Add focused unit tests and a documented command that runs them.")

def rule_metadata(s):
    if not any(p in s.files for p in ("pyproject.toml", "package.json", "Cargo.toml", "go.mod", "setup.py")):
        yield finding("package.metadata_present", "Package metadata is present", "build", "warning", "No supported ecosystem manifest was detected.", "Add package metadata with name, version, license, and reproducible development commands.")

def rule_release(s):
    if not any(p.lower() in {"changelog.md", "changes.md", "history.md"} for p in s.files):
        yield finding("release.changelog_present", "Release history is present", "release", "warning", "No CHANGELOG, CHANGES, or HISTORY file was found.", "Record user-visible changes and link releases to the changelog.")

def rule_large(s):
    for p, size in s.file_sizes.items():
        if size > 5_000_000:
            yield finding("repo.no_large_tracked_artifacts", "Large artifacts are controlled", "hygiene", "warning", f"Tracked file {p} is {size} bytes.", "Move generated/binary artifacts to a release or artifact store and keep source repositories reviewable.", evidence(p))

RULES: tuple[tuple[str, Rule], ...] = (("license.present", rule_license), ("docs.readme_present", rule_readme), ("community.contributing_present", rule_contributing), ("security.policy_present", rule_security), ("community", rule_community), ("ci", rule_ci), ("tests", rule_tests), ("package", rule_metadata), ("release", rule_release), ("hygiene", rule_large))


def audit(snapshot: RepositorySnapshot, policy: Policy | None = None) -> Report:
    policy = policy or Policy()
    findings: list[Finding] = []
    diagnostics: list[str] = []
    for _, rule in RULES:
        try:
            for item in rule(snapshot):
                if item.rule_id in policy.ignored_rules:
                    continue
                sev = policy.severity_overrides.get(item.rule_id, item.severity)
                if sev not in SEVERITIES:
                    diagnostics.append(f"invalid severity override for {item.rule_id}: {sev}")
                    sev = item.severity
                findings.append(Finding(**{**asdict(item), "severity": sev, "evidence": tuple(item.evidence)}))
        except Exception as exc:
            diagnostics.append(f"rule failure: {type(exc).__name__}: {exc}")
    findings.sort(key=lambda x: (-SEVERITY_RANK[x.severity], x.rule_id, x.fingerprint))
    blocked = any(SEVERITY_RANK[f.severity] >= SEVERITY_RANK[policy.threshold] for f in findings) if policy.threshold in SEVERITY_RANK else True
    verdict = "block" if blocked else ("review" if findings else "pass")
    return Report("0.1.0", snapshot.digest, verdict, tuple(findings), tuple(diagnostics))


def diff_reports(before: Report, after: Report) -> dict:
    old = {f.fingerprint for f in before.findings}
    new = {f.fingerprint for f in after.findings}
    return {"before": before.snapshot_digest, "after": after.snapshot_digest, "added": sorted(new - old), "resolved": sorted(old - new), "unchanged": sorted(old & new)}
