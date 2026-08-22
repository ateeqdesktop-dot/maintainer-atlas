# Maintainer Atlas

> **Make Open Source readiness inspectable.**

Maintainer Atlas is a local-first, evidence-backed auditor for Open Source repositories. It checks whether a repository is understandable, buildable, testable, maintainable, and safe to contribute to, then emits deterministic JSON, Markdown, SARIF, and snapshot-diff reports.

It is intentionally not another popularity score, vulnerability scanner, observability dashboard, or hosted service. Atlas reads repository metadata and bounded text files, never executes repository code, never installs dependencies, never follows links, and never uploads source.

## Why Atlas exists

Security scanners answer an important question, but maintainers also need to know whether a new contributor can discover the license, install the project, run tests, report a vulnerability, understand ownership, and trust the release process. Atlas turns those maintainer contracts into reviewable findings with repository-relative evidence.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
maintainer-atlas audit .
```

Generate machine-readable output for CI:

```bash
maintainer-atlas audit . --format json --output atlas.json --snapshot baseline.json
maintainer-atlas audit . --format sarif --output maintainer-atlas.sarif
maintainer-atlas diff baseline.json atlas.json
```

Exit codes are stable: `0` means pass, `1` means review findings below the configured threshold, and `2` means blocking findings or invalid input.

## Built-in checks

| Area | Examples |
|---|---|
| Governance | License, security policy, contribution guide |
| Documentation | README, installation and quickstart guidance |
| Community | Code of Conduct, issue templates, pull request template, CODEOWNERS |
| Delivery | GitHub Actions presence and mutable action tags |
| Quality | Discoverable automated tests and ecosystem metadata |
| Release | Changelog and version/release metadata |
| Hygiene | Oversized tracked artifacts |

The output is evidence-backed rather than an opaque score. Each finding includes a stable rule ID, severity, remediation, and a path/line reference where applicable.

## Policy

Create a small JSON policy file to suppress or tune findings without changing repository content:

```json
{
  "threshold": "error",
  "ignore": ["security.policy_present"],
  "severity": {"release.changelog_present": "error"},
  "waivers": {"community.code_of_conduct": "2027-01-01"}
}
```

```bash
maintainer-atlas audit . --policy atlas-policy.json
```

## GitHub Action

```yaml
name: Maintainer Atlas
on: [push, pull_request]
jobs:
  readiness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ateeqdesktop-dot/maintainer-atlas@v0.1.0
```

For high-assurance workflows, pin third-party actions to commit SHAs according to your organization policy.

## Architecture and security

See [`docs/architecture.md`](docs/architecture.md) for the system design and [`docs/product-spec.md`](docs/product-spec.md) for product boundaries. The passive loader uses a single bounded directory walk, skips symlinks and generated directories, caps file count and file size, and treats all repository content as untrusted data. YAML-like content and scripts are parsed only as text; they are never executed.

## Development

```bash
python -m pip install -e .
python -m pytest
python -m maintainer_atlas audit examples/healthy --format markdown
```

## Roadmap

Planned extensions include ecosystem-specific rule packs, signed snapshots, a GitHub metadata adapter, contributor journey checks, opt-in sandboxed reproducibility probes, and GitHub Checks annotations. The local-first core will remain usable without an account or hosted service.

## License

MIT. See [`LICENSE`](LICENSE).
