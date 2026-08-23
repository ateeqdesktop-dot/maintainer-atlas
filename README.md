# Maintainer Atlas

> **Make Open Source readiness inspectable.**

Maintainer Atlas is a local-first, evidence-backed auditor for open-source repositories. Its passive audit checks whether a repository is understandable, maintainable, testable, documented, and safe to contribute to. **Atlas Probe** adds an explicit, bounded contributor-readiness run that verifies declared installation and test commands, then emits a portable evidence bundle.

The project is intentionally not a popularity score, vulnerability scanner, observability dashboard, hosted service, or general-purpose CI runner. It complements tools such as [OpenSSF Scorecard](https://scorecard.dev/), [zizmor](https://docs.zizmor.sh/), actionlint, and GitHub artifact attestations by focusing on a different question: **can an independent contributor reproduce the documented path from a clean checkout to a useful quality signal?**

## Why it exists

A repository may have a license, a README, CI, and a test directory while its quickstart is stale or impossible to reproduce. Maintainers need reviewable evidence rather than an opaque score; contributors need a fast local check before investing time; and platform teams need CI output that does not upload source to a third-party service.

Atlas therefore has two deliberately different modes. `audit` is passive-by-default and never executes repository code. `probe` is opt-in and executes only an explicit, validated plan with bounded time and output. The distinction is visible in both the CLI and the evidence.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
maintainer-atlas audit .
```

Generate machine-readable passive evidence:

```bash
maintainer-atlas audit . --format json --output atlas.json --snapshot baseline.json
maintainer-atlas audit . --format sarif --output maintainer-atlas.sarif
maintainer-atlas diff baseline.json atlas.json
```

## Atlas Probe

Copy the example plan and run it explicitly:

```bash
cp .atlas-probe.toml.example .atlas-probe.toml
maintainer-atlas probe . --dry-run
maintainer-atlas probe . --format json --output atlas-probe.json
maintainer-atlas probe . --format markdown --output atlas-probe.md
```

A plan uses array-form commands, never shell strings:

```toml
version = 1
profile = "python"
timeout_seconds = 120
max_output_bytes = 65536
network = "deny"

[[steps]]
id = "tests"
command = ["python", "-m", "pytest", "-q"]
```

The MVP records command identity, status, exit code, duration, output sizes, SHA-256 output digests, configuration digest, and an evidence digest. Raw output is excluded unless `--include-output` is explicitly requested, and even then only a bounded preview is included.

## Built-in passive checks

| Area | Examples |
|---|---|
| Governance | License, security policy, contribution guide |
| Documentation | README and installation or quickstart guidance |
| Community | Code of Conduct, issue templates, pull request template, CODEOWNERS |
| Delivery | GitHub Actions presence and mutable action tags |
| Quality | Discoverable automated tests and ecosystem metadata |
| Release | Changelog and version/release metadata |
| Hygiene | Oversized tracked artifacts |

Each finding includes a stable rule ID, severity, remediation, fingerprint, and repository-relative evidence. Exit codes are stable: `0` means pass, `1` means review, and `2` means a blocking finding or invalid input.

## GitHub Action

The repository ships an action entry point for CI. Pin the action reference to an immutable release or commit according to your organization policy:

```yaml
name: Maintainer Atlas
on: [push, pull_request]
jobs:
  readiness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ateeqdesktop-dot/maintainer-atlas@v0.1.0
        with:
          args: audit . --format sarif --output maintainer-atlas.sarif
```

For probes, keep the plan reviewed in the repository and run it as a separate, clearly named job. The MVP treats `network = "deny"` as a policy signal; reliable OS-level network isolation requires the future container execution profile and is not falsely claimed by the local process runner.

## Security and privacy

Repository content is untrusted data. Passive scanning never executes scripts, installs dependencies, follows links, or uploads source. Probe execution is opt-in, uses `shell=False`, a fixed repository working directory, an allowlisted environment, sequential steps, bounded command count, bounded timeout, bounded output, and explicit diagnostics for limitations. The project does not provide a security sandbox in the MVP.

No telemetry leaves the machine. Canonical evidence is designed for review and comparison: volatile timestamps are not part of the evidence digest, output is represented by digests and sizes by default, and configuration and result structures use stable JSON serialization.

## Architecture

See [`docs/atlas-probe-design.md`](docs/atlas-probe-design.md) for the product specification, data flow, error model, security model, testing strategy, and roadmap. The passive loader remains bounded to 5,000 files and 256 KB text reads and skips symlinks and generated directories.

## Development

```bash
python -m pip install -e '.[dev]'
python -m pytest -q
python -m maintainer_atlas audit examples/healthy --format markdown
```

The test suite covers passive audit contracts, stable fingerprints, TOML validation, dry runs, deterministic evidence digests, optional failures, timeouts, output limits, and CLI exit codes.

## Roadmap

The next releases will add contributor-journey suggestions derived from repository documentation, ecosystem-specific probe profiles, baseline regression diffs for probe evidence, GitHub Checks annotations, and signed bundles. Later work may add containerized execution and integrations with artifact attestations. The local-first core will remain usable without an account or hosted service.

## License

MIT. See [`LICENSE`](LICENSE).
